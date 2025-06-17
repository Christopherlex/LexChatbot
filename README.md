# Lex: Trading & Scraping Chatbot Agent

Lex is a Python-based chatbot application that combines three core functionalities:

1. 💬 **Conversational Chatbot** (powered by a local LLM via LM Studio)  
2. 🐦 **Twitter Scraping** using keywords  
3. 📈 **Trading Simulation** through MetaTrader 5 integration  

---

## 🔧 Features

- GUI Chat Interface (Tkinter-based)
- Automatic intent detection (Chat / Scraping / Trading)
- Twitter search via keywords
- Technical trading analysis simulation
- Fully offline-capable with LM Studio support

---

## 📂 Files Included

- `main.py` – Main GUI and controller  
- `Scrapper.py` – Twitter scraping logic  
- `Trading.py` – MetaTrader 5 integration  
- `credentials.json` – Twitter login details  

---

## 🚀 Quick Start

1. Install Python 3.9+ from [python.org](https://www.python.org/)
2. Donwload all the file and out it in a folder
3. Install dependencies:
   ```bash
   pip install tkinter openai python-mt5 tweepy pandas numpy tensorflow
   pip install selenium webdriver-manager transformers torch
   pip install MetaTrader5 pandas-ta matplotlib psutil pywin32
4. Install LM Studio and load a model like qwen2.5-7b-instruct
5. Run MetaTrader 5 from metatrader5.com
6. Launch the app:
7. ```bash
   python main.py

## Commands Overview
Functionality	Example Command
Chatbot	"Tell me a joke"
Twitter Scraping	"Scrape tweets"
Trading Simulation	"Run technical analysis"
Exit Application	"quit"

## Full Documentation
For detailed setup, configuration, and usage instructions, please refer to the PDF manual:
👉 documentation of LEX.pdf

