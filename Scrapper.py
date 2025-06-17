import json
import time
import random
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from transformers import pipeline
import torch

# Load Twitter credentials from a JSON file
def load_credentials():
    with open("credentials.json", "r") as file:
        return json.load(file)

# Set up the browser driver
def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

# Login to Twitter, handle extra email verification step
def login_twitter(driver, username, password):
    driver.get("https://twitter.com/login")
    wait = WebDriverWait(driver, 20)
    
    # Step 1: Enter username
    username_input = wait.until(EC.presence_of_element_located((By.NAME, "text")))
    username_input.send_keys(username)
    username_input.send_keys(Keys.RETURN)
    time.sleep(2)

    # Step 2: Check for email/phone verification prompt
    try:
        verify_input = wait.until(EC.presence_of_element_located((By.NAME, "text")))
        verify_input.clear()
        verify_input.send_keys("c13230018@john.petra.ac.id")
        verify_input.send_keys(Keys.RETURN)
        time.sleep(2)
    except:
        print("No additional email verification step detected.")

    # Step 3: Enter password
    password_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))
    password_input.send_keys(password)
    password_input.send_keys(Keys.RETURN)
    time.sleep(5)

# Search for tweets
def search_tweets(driver, keyword, num_tweets=100, lang="en"):
    search_url = f"https://twitter.com/search?q={keyword}&lang={lang}&f=live"
    driver.get(search_url)
    time.sleep(3)
    
    tweets = set()
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while len(tweets) < num_tweets:
        elements = driver.find_elements(By.XPATH, "//article//div[@lang]")
        for el in elements:
            tweets.add(el.text)
            if len(tweets) >= num_tweets:
                break
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(2, 4))
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        if new_height == last_height:
            break
        last_height = new_height
    
    return list(tweets)

# Sentiment analysis using BERT
bert_classifier = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")

def analyze_sentiment(tweets, update_callback=None):
    bert_results = {"positive": 0, "neutral": 0, "negative": 0}
    display = ""

    for i, tweet in enumerate(tweets[:5]):  # Show first 5 tweets
        bert_prediction = bert_classifier(tweet)[0]['label']
        if "1 star" in bert_prediction or "2 star" in bert_prediction:
            sentiment = "Negative"
        elif "4 star" in bert_prediction or "5 star" in bert_prediction:
            sentiment = "Positive"
        else:
            sentiment = "Neutral"
        bert_results[sentiment.lower()] += 1

        line = f"📝 {tweet[:120]}...\n📊 Sentiment: {sentiment}\n"
        display += line
        if update_callback:
            update_callback(line)

    total = len(tweets)
    if total == 0:
        return "❌ No tweets found."

    summary = (f"\n✅ Sentiment Summary:\n"
               f"Positive: {bert_results['positive'] / total * 100:.1f}%\n"
               f"Neutral: {bert_results['neutral'] / total * 100:.1f}%\n"
               f"Negative: {bert_results['negative'] / total * 100:.1f}%\n")
    return summary

# ✅ Entry point for GUI chatbot
def run_scraper_interactive(keyword, num_tweets, lang, update_callback):
    credentials = load_credentials()
    driver = init_driver()
    try:
        update_callback("🔐 Logging into Twitter...")
        login_twitter(driver, credentials["username"], credentials["password"])
        
        update_callback(f"🔍 Scraping tweets for '{keyword}' in '{lang}'...")
        tweets = search_tweets(driver, keyword, num_tweets, lang)
        update_callback(f"✅ Fetched {len(tweets)} tweets.")
        
        update_callback("📊 Analyzing sentiment with BERT...")
        result = analyze_sentiment(tweets, update_callback)
        update_callback(result)
    except Exception as e:
        update_callback(f"❌ Error: {e}")
    finally:
        driver.quit()
