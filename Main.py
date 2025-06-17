import os
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox, simpledialog, Canvas, Frame, Scrollbar
from openai import OpenAI
import Scrapper

# === ENV SETUP ===
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
model = "lmstudio-community/qwen2.5-7b-instruct"

class LexandChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Lex Chatbot")
        self.root.geometry("800x650")
        self.root.configure(bg="#F5F5F5")

        # === Chat Area ===
        self.chat_frame = tk.Frame(self.root, bg="#F5F5F5")
        self.chat_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = Canvas(self.chat_frame, bg="#F5F5F5", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = Scrollbar(self.chat_frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scroll_frame = Frame(self.canvas, bg="#F5F5F5")
        self.scroll_window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")

        self.scroll_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # === Input Area (Stays at bottom) ===
        self.input_frame = tk.Frame(self.root, bg="#FFFFFF", bd=1, relief=tk.SOLID)
        self.input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        self.user_input = tk.Entry(self.input_frame, font=("Segoe UI", 12), relief=tk.FLAT)
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 5), pady=10)
        self.user_input.bind("<Return>", self.send_message)

        self.send_button = tk.Button(self.input_frame, text="Send", font=("Segoe UI", 11, "bold"),
                                     bg="#4CAF50", fg="white", relief=tk.FLAT, width=10,
                                     command=self.send_message)
        self.send_button.pack(side=tk.RIGHT, padx=(5, 10), pady=10)

        self.append_bubble("🤖", "Hello! I'm Lex chatbot.\nI can help with Twitter scraping, trading simulations, or general chat.", "left")

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(1.0)

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.scroll_window, width=event.width)

    def append_bubble(self, avatar, message, side):
        bubble_frame = tk.Frame(self.scroll_frame, bg="#F5F5F5", pady=5)
        bubble_frame.pack(anchor="e" if side == "right" else "w", padx=12, pady=3, fill=tk.X)

        icon = tk.Label(bubble_frame, text=avatar, font=("Segoe UI", 14), bg="#F5F5F5")
        icon.pack(side=tk.RIGHT if side == "right" else tk.LEFT)

        bubble_color = "#DCF8C6" if side == "right" else "#FFFFFF"
        text_label = tk.Label(
            bubble_frame,
            text=message,
            font=("Segoe UI", 11),
            bg=bubble_color,
            wraplength=500,
            justify=tk.LEFT,
            anchor="w",
            padx=12,
            pady=8,
            relief=tk.SOLID,
            bd=1
        )
        text_label.pack(side=tk.RIGHT if side == "right" else tk.LEFT, padx=(5, 0))

        self.root.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def send_message(self, event=None):
        user_text = self.user_input.get().strip()
        if not user_text:
            return

        self.append_bubble("🙂", user_text, "right")
        self.user_input.delete(0, tk.END)

        if user_text.lower() == "quit":
            self.append_bubble("🤖", "Goodbye!", "left")
            self.root.after(1000, self.root.destroy)
            return

        lower = user_text.lower()
        if any(k in lower for k in ["scrape", "twitter scraper", "scrapes", "tweets", "news scraping","twitter scraping"]):
            self.confirm_and_run("Twitter Scraper", "Do you want to run the Twitter Scraper?", self.run_scraper_gui)
        elif any(k in lower for k in ["technical analysis", "trading simulation", "run trading", "start trading"]):
            self.confirm_and_run("Trading Simulation", "Do you want to start the Trading Simulation? (MetaTrader 5 required)", self.run_trader_script)
        else:
            threading.Thread(target=self.ask_lmstudio, args=(user_text,)).start()

    def confirm_and_run(self, title, prompt, function_to_run):
        confirm = messagebox.askyesno(title, prompt)
        if confirm:
            self.append_bubble("🤖", f"{title} started...", "left")
            self.root.after(100, function_to_run)
        else:
            self.append_bubble("🤖", f"Okay, I won’t run {title.lower()}.", "left")

    def run_scraper_gui(self):
        keyword = simpledialog.askstring("Twitter Keyword", "Enter keyword:")
        if not keyword:
            return self.append_bubble("🤖", "Cancelled: no keyword entered.", "left")

        num = simpledialog.askinteger("Number of Tweets", "How many tweets?", minvalue=1, maxvalue=5)
        if not num:
            return self.append_bubble("🤖", "Cancelled: no tweet number entered.", "left")

        lang = simpledialog.askstring("Language Code", "Enter language code (default: en):") or "en"

        self.append_bubble("🤖", f"Running Twitter scraper for '{keyword}' ({num} tweets in {lang})...", "left")

        def threaded_run():
            try:
                Scrapper.run_scraper_interactive(keyword, num, lang, self.append_bubble_from_bot)
            except Exception as e:
                self.append_bubble("🤖", f"Error: {e}", "left")

        threading.Thread(target=threaded_run).start()

    def run_trader_script(self):
        try:
            subprocess.run(["python", "Trading.py"])
            self.append_bubble("🤖", "Trading simulation completed.", "left")
        except Exception as e:
            self.append_bubble("🤖", f"Error running trading simulation: {e}", "left")

    def ask_lmstudio(self, user_text):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": user_text}],
            )
            message = response.choices[0].message.content
            self.append_bubble("🤖", message, "left")
        except Exception as e:
            self.append_bubble("🤖", f"Error: {e}", "left")

    def append_bubble_from_bot(self, message):
        self.append_bubble("🤖", message, "left")

if __name__ == "__main__":
    root = tk.Tk()
    app = LexandChatApp(root)
    root.mainloop()
