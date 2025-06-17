import unittest
from unittest.mock import patch
import Trading
import pandas as pd

class TestTradingBot(unittest.TestCase):
    def setUp(self):
        self.bot = Trading.GoldTradingBot(demo_account=False)
        self.bot.connect_mt5 = lambda: None
        self.bot.launch_mt5 = lambda: None
        self.bot.setup_gui = lambda: None
        self.bot.ensure_chart_open = lambda: None

    def test_analyze_signal_buy(self):
        df = pd.DataFrame([
            {'close': 100, 'EMA50': 90, 'EMA100': 80, 'MACD_12_26_9': 0.5, 'MACDs_12_26_9': 0.4, 'RSI': 55, 'ATR': 2},
            {'close': 99, 'EMA50': 89, 'EMA100': 79, 'MACD_12_26_9': 0.4, 'MACDs_12_26_9': 0.4, 'RSI': 52, 'ATR': 2}
        ])
        signal, sl, tp = self.bot.analyze_signal(df)
        self.assertEqual(signal, 'BUY')
        self.assertLess(sl, tp)

    def test_execute_trade_invalid_stop_loss(self):
        result = self.bot.execute_simulated_trade('BUY', 100, 105, 110)
        self.assertFalse(result)

    def test_execute_trade_valid_sell(self):
        result = self.bot.execute_simulated_trade('SELL', 100, 105, 90)
        self.assertTrue(result)


    def test_check_open_positions(self):
        self.bot.simulated_positions = [{'type': 'BUY', 'entry_price': 100}]
        pos = self.bot.check_open_positions()
        self.assertEqual(pos['type'], 'BUY')
