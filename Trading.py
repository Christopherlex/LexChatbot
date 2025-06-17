import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
import time
import numpy as np
import os
import subprocess
import psutil
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import ttk
import threading
from typing import Tuple, Optional, List
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.gridspec import GridSpec

plt.style.use('dark_background')

class GoldTradingBot:
    def __init__(self, symbol: str = "XAUUSD", timeframe: int = mt5.TIMEFRAME_M1,
                 risk_per_trade: float = 10.0, tp_factor: float = 1.5, 
                 demo_account: bool = True, mt5_path: str = None):
        """
        Initialize the Gold Trading Bot with MT5 connection and parameters.
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.risk_per_trade = risk_per_trade  # Fixed $10 risk per trade
        self.tp_factor = tp_factor
        self.in_position = False
        self.position_type = None
        self.entry_price = 0
        self.entry_time = None
        self.win_count = 0
        self.loss_count = 0
        self.total_trades = 0
        self.equity = []
        self.mt5_path = mt5_path or self.detect_mt5_path()
        self.demo_account = demo_account
        
        # For simulation
        self.simulated_balance = 10000  # Starting with $10,000
        self.simulated_positions = []
        self.signal_history = []
        
        self.launch_mt5()
        self.connect_mt5()
        self.ensure_chart_open()
        
        # Initialize GUI
        self.setup_gui()
        
    def detect_mt5_path(self) -> str:
        """Try to automatically detect MT5 installation path."""
        common_paths = [
            r"C:\Program Files\MetaTrader 5\terminal64.exe",
            r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\MetaTrader 5\terminal64.exe"),
            r"C:\Program Files\MetaTrader 5\terminal.exe",
            r"C:\Program Files (x86)\MetaTrader 5\terminal.exe"
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None
        
    def launch_mt5(self) -> None:
        """Launch MetaTrader 5 if not already running."""
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] in ['terminal.exe', 'terminal64.exe']:
                print("MT5 is already running")
                return
                
        if not self.mt5_path:
            raise FileNotFoundError("Could not find MetaTrader 5 executable. Please specify path.")
            
        print(f"Launching MT5 from: {self.mt5_path}")
        try:
            subprocess.Popen([self.mt5_path])
            print("Waiting for MT5 to initialize...")
            time.sleep(15)  # Give MT5 time to start
        except Exception as e:
            print(f"Failed to launch MT5: {e}")
            raise
            
    def ensure_chart_open(self) -> None:
        try:
            print(f"Opening chart for {self.symbol} {self.timeframe}")
            time.sleep(5)  # Allow chart to open
            self.bring_mt5_to_foreground()
        except Exception as e:
            print(f"Error in ensure_chart_open: {e}")
            
    def bring_mt5_to_foreground(self) -> None:
        """Attempt to bring MT5 window to foreground (Windows only)."""
        try:
            import win32gui
            import win32con
            
            def callback(hwnd, extra):
                if "MetaTrader 5" in win32gui.GetWindowText(hwnd):
                    extra.append(hwnd)
                return True
                
            windows = []
            win32gui.EnumWindows(callback, windows)
            
            if windows:
                hwnd = windows[0]
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                print("MT5 window brought to foreground")
        except ImportError:
            print("Install pywin32 to automatically bring MT5 window to foreground")
        except Exception as e:
            print(f"Could not bring MT5 window to foreground: {e}")
            
    def connect_mt5(self) -> None:
        """Connect to MT5 terminal and initialize account."""
        if not mt5.initialize():
            print("Initialize failed:", mt5.last_error())
            quit()
        
        if self.demo_account:
            # Replace with your actual demo account credentials
            account = 5035923969  # Your demo account number
            password = "7eIqSh*k"  # Your demo account password
            server = "MetaQuotes-Demo" # Your demo server name
            
            authorized = mt5.login(account, password=password, server=server)
            if not authorized:
                print("Failed to connect to account: ", mt5.last_error())
                mt5.shutdown()
                quit()
        
        print(f"Connected to MT5, account #{mt5.account_info().login}")
        
    def get_market_data(self, bars: int = 500) -> pd.DataFrame:
        """Fetch market data and calculate indicators."""
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
        if rates is None:
            print("Failed to get rates:", mt5.last_error())
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Calculate indicators - Only MA, RSI, and MACD
        df['EMA50'] = ta.ema(df['close'], length=50)
        df['EMA100'] = ta.ema(df['close'], length=100)
        df['RSI'] = ta.rsi(df['close'], length=14)
        
        # MACD
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        df = pd.concat([df, macd], axis=1)
        
        # ATR for stop loss calculation
        atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['ATR'] = atr
        
        return df.dropna()
    
    def analyze_signal(self, df: pd.DataFrame) -> Tuple[str, float, float]:
        """
        Analyze market conditions using weighted MCDM approach with multiple indicators.
        Improved trading logic with dynamic TP/SL optimization.
        """
        last = df.iloc[-1]
        prev = df.iloc[-2]
        signal = 'HOLD'
        stop_loss = 0
        take_profit = 0
        
        # Calculate dynamic stop loss based on ATR and recent volatility
        atr_multiplier = self.optimize_atr_multiplier(df)
        atr_stop = last['ATR'] * atr_multiplier
        
        # Weighted MCDM scoring system (0-100 scale)
        buy_score = 0
        sell_score = 0
        
        # 1. Trend Strength (40% weight)
        # - EMA crossover confirmation
        ema_cross_weight = 0.4
        if last['EMA50'] > last['EMA100'] and prev['EMA50'] <= prev['EMA100']:
            buy_score += 40 * ema_cross_weight  # Strong bullish crossover
        elif last['EMA50'] < last['EMA100'] and prev['EMA50'] >= prev['EMA100']:
            sell_score += 40 * ema_cross_weight  # Strong bearish crossover
        elif last['EMA50'] > last['EMA100']:
            buy_score += 20 * ema_cross_weight  # Existing bullish trend
        elif last['EMA50'] < last['EMA100']:
            sell_score += 20 * ema_cross_weight  # Existing bearish trend
            
        # 2. Momentum (30% weight)
        # - RSI with dynamic thresholds based on recent volatility
        rsi_weight = 0.3
        rsi_buy_threshold = 40 - (last['ATR'] / last['close'] * 1000)  # Dynamic threshold
        rsi_sell_threshold = 60 + (last['ATR'] / last['close'] * 1000)
        
        if last['RSI'] > rsi_buy_threshold and last['RSI'] < 70:
            buy_score += (last['RSI'] - rsi_buy_threshold) / (70 - rsi_buy_threshold) * 30 * rsi_weight
        if last['RSI'] < rsi_sell_threshold and last['RSI'] > 30:
            sell_score += (rsi_sell_threshold - last['RSI']) / (rsi_sell_threshold - 30) * 30 * rsi_weight
            
        # 3. MACD Confirmation (20% weight)
        macd_weight = 0.2
        macd_buy_signal = (
            last['MACD_12_26_9'] > last['MACDs_12_26_9'] and 
            prev['MACD_12_26_9'] <= prev['MACDs_12_26_9'] and
            last['MACD_12_26_9'] > 0
        )
        macd_sell_signal = (
            last['MACD_12_26_9'] < last['MACDs_12_26_9'] and 
            prev['MACD_12_26_9'] >= prev['MACDs_12_26_9'] and
            last['MACD_12_26_9'] < 0
        )
        
        if macd_buy_signal:
            buy_score += 20 * macd_weight
        if macd_sell_signal:
            sell_score += 20 * macd_weight
            
        # 4. Price Action (10% weight)
        price_weight = 0.1
        # Bullish candle patterns
        if last['close'] > last['open'] and (last['close'] - last['open']) > (0.5 * last['ATR']):
            buy_score += 10 * price_weight
        # Bearish candle patterns
        elif last['close'] < last['open'] and (last['open'] - last['close']) > (0.5 * last['ATR']):
            sell_score += 10 * price_weight
            
        # Generate signal only if score exceeds threshold (60/100)
        signal_threshold = 60
        if buy_score >= signal_threshold and buy_score > sell_score:
            signal = 'BUY'
            stop_loss, take_profit = self.calculate_optimal_levels(df, 'BUY')
            
        elif sell_score >= signal_threshold and sell_score > buy_score:
            signal = 'SELL'
            stop_loss, take_profit = self.calculate_optimal_levels(df, 'SELL')
            
        return signal, stop_loss, take_profit
    
    def calculate_optimal_levels(self, df: pd.DataFrame, signal_type: str) -> Tuple[float, float]:
        """
        Calculate optimal TP/SL levels based on:
        1. Recent support/resistance levels
        2. Volatility-adjusted ATR
        3. Recent price swings
        """
        last = df.iloc[-1]
        atr = last['ATR']
        close = last['close']
        
        # Dynamic risk-reward ratio based on market conditions
        volatility_factor = atr / close
        recent_trend_strength = self.calculate_trend_strength(df)
        
        # Base values
        base_sl_distance = atr * 1.5  # Start with 1.5 ATR
        
        # Adjust SL based on recent volatility
        if volatility_factor > 0.005:  # High volatility
            sl_multiplier = 1.2
        else:  # Low volatility
            sl_multiplier = 1.8
            
        # Adjust TP based on trend strength
        if recent_trend_strength > 0.7:  # Strong trend
            tp_multiplier = 2.5
        elif recent_trend_strength > 0.3:  # Moderate trend
            tp_multiplier = 2.0
        else:  # Weak trend
            tp_multiplier = 1.5
            
        # Calculate final levels
        if signal_type == 'BUY':
            stop_loss = close - (base_sl_distance * sl_multiplier)
            take_profit = close + (base_sl_distance * tp_multiplier)
            
            # Adjust to nearest support/resistance
            recent_lows = df['low'].rolling(20).min().iloc[-1]
            if stop_loss < recent_lows:
                stop_loss = recent_lows - (0.2 * atr)  # Give some buffer
                
            recent_highs = df['high'].rolling(20).max().iloc[-1]
            if take_profit > recent_highs:
                take_profit = recent_highs + (0.2 * atr)
                
        else:  # SELL
            stop_loss = close + (base_sl_distance * sl_multiplier)
            take_profit = close - (base_sl_distance * tp_multiplier)
            
            # Adjust to nearest support/resistance
            recent_highs = df['high'].rolling(20).max().iloc[-1]
            if stop_loss > recent_highs:
                stop_loss = recent_highs + (0.2 * atr)
                
            recent_lows = df['low'].rolling(20).min().iloc[-1]
            if take_profit < recent_lows:
                take_profit = recent_lows - (0.2 * atr)
                
        return stop_loss, take_profit
    
    def calculate_trend_strength(self, df: pd.DataFrame) -> float:
        """
        Calculate trend strength (0-1) based on:
        1. EMA slope
        2. Price/EMA distance
        3. Consecutive candles in trend direction
        """
        # EMA slope calculation
        ema_slope = (df['EMA50'].iloc[-1] - df['EMA50'].iloc[-5]) / 5
        
        # Price distance from EMA
        price_distance = abs(df['close'].iloc[-1] - df['EMA50'].iloc[-1]) / df['EMA50'].iloc[-1]
        
        # Consecutive candles in trend direction
        trend_candles = 0
        for i in range(1, 6):
            if df['close'].iloc[-i] > df['open'].iloc[-i]:
                trend_candles += 1 if ema_slope > 0 else -1
            else:
                trend_candles += -1 if ema_slope > 0 else 1
                
        # Normalize to 0-1 range
        trend_strength = (
            0.4 * min(abs(ema_slope) / (df['close'].iloc[-1] * 0.01), 1) +  # Cap at 1
            0.3 * min(price_distance / 0.02, 1) +  # Cap at 2% distance
            0.3 * min(abs(trend_candles) / 5, 1)   # Cap at 5 candles
        )
        
        return min(trend_strength, 1)  # Ensure maximum 1
    
    def optimize_atr_multiplier(self, df: pd.DataFrame) -> float:
        """
        Dynamically adjust ATR multiplier based on recent win rate and market conditions
        """
        if len(self.signal_history) < 5:
            return 1.5  # Default value
            
        # Calculate recent win rate
        recent_trades = [t for t in self.signal_history[-5:] if 'result' in t]
        if not recent_trades:
            return 1.5
            
        win_rate = sum(1 for t in recent_trades if t['result'] == 'win') / len(recent_trades)
        
        # Adjust multiplier based on win rate
        if win_rate > 0.7:  # High win rate - can afford tighter stops
            return 1.2
        elif win_rate < 0.3:  # Low win rate - need wider stops
            return 2.0
        else:  # Moderate win rate
            return 1.5
    
    def execute_simulated_trade(self, signal: str, price: float, 
                              stop_loss: float, take_profit: float) -> bool:
        """Simulate a trade with fixed $10 risk."""
        # Calculate position size based on stop distance
        if signal == 'BUY':
            risk_per_unit = price - stop_loss
        else:  # SELL
            risk_per_unit = stop_loss - price
            
        if risk_per_unit <= 0:
            print("Invalid stop loss - trade not executed")
            return False
            
        # Calculate units to risk exactly $10
        units = self.risk_per_trade / risk_per_unit
        
        # In simulation, we just record the trade
        self.simulated_positions.append({
            'type': signal,
            'entry_price': price,
            'sl': stop_loss,
            'tp': take_profit,
            'entry_time': datetime.now(),
            'units': units
        })
        
        print(f"SIMULATED TRADE: {signal} {self.symbol} at {price:.2f}")
        print(f"Units: {units:.2f} | Stop Loss: {stop_loss:.2f} | Take Profit: {take_profit:.2f}")
        return True
    
    def check_open_positions(self) -> Optional[dict]:
        """Check for open simulated positions."""
        return self.simulated_positions[-1] if self.simulated_positions else None
    
    def monitor_simulated_trades(self) -> None:
        """Monitor simulated trades."""
        if not self.simulated_positions:
            self.in_position = False
            return
            
        position = self.simulated_positions[-1]
        current_price = mt5.symbol_info_tick(self.symbol).ask if position['type'] == 'BUY' else mt5.symbol_info_tick(self.symbol).bid
        
        # Check for TP/SL hit
        if (position['type'] == 'BUY' and 
            (current_price >= position['tp'] or current_price <= position['sl'])):
            self._close_simulated_position(position, current_price)
            
        elif (position['type'] == 'SELL' and 
              (current_price <= position['tp'] or current_price >= position['sl'])):
            self._close_simulated_position(position, current_price)
    
    def _close_simulated_position(self, position, current_price: float) -> None:
        """Close a simulated position."""
        if position['type'] == 'BUY':
            profit = (current_price - position['entry_price']) * position['units']
        else:
            profit = (position['entry_price'] - current_price) * position['units']
            
        self.simulated_balance += profit
        
        if profit > 0:
            self.win_count += 1
            result = 'win'
        else:
            self.loss_count += 1
            result = 'loss'
        self.total_trades += 1
        self.in_position = False
        
        # Record trade result in signal history
        for signal in reversed(self.signal_history):
            if signal.get('price') == position['entry_price'] and signal.get('time') == position['entry_time']:
                signal['result'] = result
                break
        
        print(f"SIMULATED POSITION CLOSED: {'Profit' if profit > 0 else 'Loss'} of ${abs(profit):.2f}")
        print(f"New simulated balance: ${self.simulated_balance:.2f}")
        
        # Remove the closed position
        self.simulated_positions.pop()
    
    def display_stats(self, df: pd.DataFrame) -> None:
        """Display trading statistics and current market info."""
        last = df.iloc[-1]
        position = self.check_open_positions()
        
        stats_text = f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        stats_text += f"Symbol: {self.symbol} | Price: {last['close']:.2f}\n"
        stats_text += "-" * 50 + "\n"
        stats_text += "INDICATORS:\n"
        stats_text += f"EMA50: {last['EMA50']:.2f} | EMA100: {last['EMA100']:.2f}\n"
        stats_text += f"RSI: {last['RSI']:.2f}\n"
        stats_text += f"MACD Line: {last['MACD_12_26_9']:.4f} | Signal: {last['MACDs_12_26_9']:.4f}\n"
        stats_text += f"ATR (Volatility): {last['ATR']:.4f}\n"
        stats_text += "-" * 50 + "\n"
        
        if position:
            stats_text += f"SIMULATED POSITION: {position['type']} at {position['entry_price']:.2f}\n"
            stats_text += f"Units: {position['units']:.2f} | SL: {position['sl']:.2f} | TP: {position['tp']:.2f}\n"
            current_price = mt5.symbol_info_tick(self.symbol).ask if position['type'] == 'BUY' else mt5.symbol_info_tick(self.symbol).bid
            pnl = (current_price - position['entry_price']) * position['units'] * (1 if position['type'] == 'BUY' else -1)
            stats_text += f"Current PnL: ${pnl:.2f}\n"
        
        if self.total_trades > 0:
            win_rate = 100 * self.win_count / self.total_trades
            profit_factor = self.win_count / self.loss_count if self.loss_count > 0 else np.inf
            stats_text += f"TRADE STATS: Win Rate: {win_rate:.2f}% | Wins: {self.win_count} | Losses: {self.loss_count}\n"
            stats_text += f"Profit Factor: {profit_factor:.2f} | Risk/Reward: 1:{self.tp_factor:.1f}\n"
        
        stats_text += f"SIMULATED BALANCE: ${self.simulated_balance:.2f}\n"
        
        # Update GUI
        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(tk.END, stats_text)
        self.stats_text.config(state=tk.DISABLED)
        
        # Update chart
        self.update_chart(df)
    
    def setup_gui(self) -> None:
        """Set up the graphical user interface."""
        self.root = tk.Tk()
        self.root.title("Gold Trading Bot - Simulation Mode")
        self.root.geometry("1200x800")
        
        # Create frames
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(side=tk.TOP, fill=tk.X)
        
        stats_frame = ttk.Frame(self.root, padding="10")
        stats_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        chart_frame = ttk.Frame(self.root)
        chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Control panel
        ttk.Label(control_frame, text="Trading Controls").pack(anchor=tk.W)
        
        ttk.Button(control_frame, text="Start Bot", command=self.start_bot).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Stop Bot", command=self.stop_bot).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Exit", command=self.shutdown).pack(side=tk.LEFT, padx=5)
        
        # Stats panel
        self.stats_text = tk.Text(stats_frame, height=30, width=60, state=tk.DISABLED)
        self.stats_text.pack(fill=tk.BOTH, expand=True)
        
        # Chart panel - Using GridSpec for multiple plots
        self.fig = plt.figure(figsize=(10, 8))
        self.gs = GridSpec(3, 1, height_ratios=[2, 1, 1])
        
        # Price chart
        self.ax_price = self.fig.add_subplot(self.gs[0])
        self.ax_price.set_title(f"{self.symbol} Price and Moving Averages")
        self.price_line, = self.ax_price.plot([], [], label='Price', color='yellow')
        self.ema50_line, = self.ax_price.plot([], [], label='EMA50', color='cyan')
        self.ema100_line, = self.ax_price.plot([], [], label='EMA100', color='magenta')
        self.ax_price.legend(loc='upper left')
        self.ax_price.grid(True, alpha=0.3)
        
        # RSI chart
        self.ax_rsi = self.fig.add_subplot(self.gs[1], sharex=self.ax_price)
        self.ax_rsi.set_title("RSI (14)")
        self.rsi_line, = self.ax_rsi.plot([], [], label='RSI', color='white')
        self.ax_rsi.axhline(70, color='red', linestyle='--', alpha=0.5)
        self.ax_rsi.axhline(30, color='green', linestyle='--', alpha=0.5)
        self.ax_rsi.axhline(50, color='gray', linestyle='--', alpha=0.3)
        self.ax_rsi.set_ylim(0, 100)
        self.ax_rsi.grid(True, alpha=0.3)
        
        # MACD chart
        self.ax_macd = self.fig.add_subplot(self.gs[2], sharex=self.ax_price)
        self.ax_macd.set_title("MACD (12,26,9)")
        self.macd_line, = self.ax_macd.plot([], [], label='MACD', color='white')
        self.signal_line, = self.ax_macd.plot([], [], label='Signal', color='orange')
        self.ax_macd.axhline(0, color='gray', linestyle='--', alpha=0.3)
        self.ax_macd.legend(loc='upper left')
        self.ax_macd.grid(True, alpha=0.3)
        
        # Trading signal markers
        self.buy_signals = self.ax_price.scatter([], [], color='green', marker='^', s=100, label='Buy')
        self.sell_signals = self.ax_price.scatter([], [], color='red', marker='v', s=100, label='Sell')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Status flag
        self.running = False
        
    def update_chart(self, df: pd.DataFrame) -> None:
        """Update the price chart with new data."""
        # Filter data for the last 24 hours
        now = datetime.now()
        last_24h = now - timedelta(hours=24)
        df_filtered = df[df['time'] >= last_24h]
        if df_filtered.empty:
            df_filtered = df  # fallback to full data if filtered empty
        
        # Clear and update price chart
        self.ax_price.clear()
        self.ax_price.plot(df_filtered['time'], df_filtered['close'], label='Price', color='yellow')
        self.ax_price.plot(df_filtered['time'], df_filtered['EMA50'], label='EMA50', color='cyan')
        self.ax_price.plot(df_filtered['time'], df_filtered['EMA100'], label='EMA100', color='magenta')
        
        # Update RSI chart
        self.ax_rsi.clear()
        self.ax_rsi.plot(df_filtered['time'], df_filtered['RSI'], label='RSI', color='white')
        self.ax_rsi.axhline(70, color='red', linestyle='--', alpha=0.5)
        self.ax_rsi.axhline(30, color='green', linestyle='--', alpha=0.5)
        self.ax_rsi.axhline(50, color='gray', linestyle='--', alpha=0.3)
        self.ax_rsi.set_ylim(0, 100)
        self.ax_rsi.set_title("RSI (14)")
        self.ax_rsi.grid(True, alpha=0.3)
        
        # Update MACD chart
        self.ax_macd.clear()
        self.ax_macd.plot(df_filtered['time'], df_filtered['MACD_12_26_9'], label='MACD', color='white')
        self.ax_macd.plot(df_filtered['time'], df_filtered['MACDs_12_26_9'], label='Signal', color='orange')
        self.ax_macd.bar(df_filtered['time'], df_filtered['MACDh_12_26_9'], 
                        color=np.where(df_filtered['MACDh_12_26_9'] > 0, 'green', 'red'), 
                        alpha=0.5, width=0.0005)
        self.ax_macd.axhline(0, color='gray', linestyle='--', alpha=0.3)
        self.ax_macd.set_title("MACD (12,26,9)")
        self.ax_macd.legend(loc='upper left')
        self.ax_macd.grid(True, alpha=0.3)
        
        # Plot signals that fall in the last 24h window
        buy_signals = [signal for signal in self.signal_history if signal['signal'] == 'BUY' and signal['time'] >= last_24h]
        sell_signals = [signal for signal in self.signal_history if signal['signal'] == 'SELL' and signal['time'] >= last_24h]
        
        if buy_signals:
            buy_times = [signal['time'] for signal in buy_signals]
            buy_prices = [signal['price'] for signal in buy_signals]
            self.ax_price.scatter(buy_times, buy_prices, color='green', marker='^', s=100, label='Buy Signal')
        
        if sell_signals:
            sell_times = [signal['time'] for signal in sell_signals]
            sell_prices = [signal['price'] for signal in sell_signals]
            self.ax_price.scatter(sell_times, sell_prices, color='red', marker='v', s=100, label='Sell Signal')
        
        # Formatting
        self.ax_price.set_title(f"{self.symbol} Price and Moving Averages (Last 24 Hours)")
        self.ax_price.legend(loc='upper left')
        self.ax_price.grid(True, alpha=0.3)
        
        # Rotate x-axis labels for better readability
        for ax in [self.ax_price, self.ax_rsi, self.ax_macd]:
            for label in ax.get_xticklabels():
                label.set_rotation(45)
                label.set_horizontalalignment('right')
        
        self.fig.tight_layout()
        self.canvas.draw()
    
    def start_bot(self) -> None:
        """Start the trading bot in a separate thread."""
        if not self.running:
            self.running = True
            self.bot_thread = threading.Thread(target=self.run_bot_loop)
            self.bot_thread.daemon = True
            self.bot_thread.start()
            print("Bot started")
    
    def stop_bot(self) -> None:
        """Stop the trading bot."""
        self.running = False
        print("Bot stopped")
    
    def run_bot_loop(self) -> None:
        """Main trading loop for the bot thread."""
        while self.running:
            df = self.get_market_data()
            if df is None:
                time.sleep(10)
                continue
            
            # Check for open positions
            self.monitor_simulated_trades()
            
            # Generate signal if not in position
            if not self.in_position:
                signal, sl, tp = self.analyze_signal(df)
                if signal in ['BUY', 'SELL']:
                    current_price = mt5.symbol_info_tick(self.symbol).ask if signal == 'BUY' else mt5.symbol_info_tick(self.symbol).bid
                    if self.execute_simulated_trade(signal, current_price, sl, tp):
                        self.in_position = True
                        self.position_type = signal
                        self.entry_price = current_price
                        self.entry_time = datetime.now()
                        
                        # Record signal for chart
                        self.signal_history.append({
                            'signal': signal,
                            'price': current_price,
                            'time': datetime.now(),
                            'sl': sl,
                            'tp': tp
                        })
            
            # Display stats
            self.display_stats(df)
            
            # Update equity curve
            self.equity.append((datetime.now(), self.simulated_balance))
            
            time.sleep(10)  # Change refresh rate to 10 seconds
    
    def shutdown(self) -> None:
        """Clean up and shut down the application."""
        self.running = False
        mt5.shutdown()
        self.root.quit()
        self.root.destroy()
        print("Application shut down")

if __name__ == "__main__":
    try:
        # Initialize and run the bot
        bot = GoldTradingBot(
            symbol="XAUUSD",
            timeframe=mt5.TIMEFRAME_M1,
            risk_per_trade=10.0,  # Fixed $10 risk per trade
            tp_factor=1.5,
            demo_account=True,
            mt5_path=None  # Add path if MT5 not in default location
        )
        
        # Start the GUI main loop
        bot.root.mainloop()
        
    except Exception as e:
        print(f"Error in main: {e}")
        mt5.shutdown()