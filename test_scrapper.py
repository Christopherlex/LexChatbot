import unittest
from unittest.mock import patch, mock_open, MagicMock
import Scrapper

class TestScrapper(unittest.TestCase):

    @patch("builtins.open", new_callable=mock_open, read_data='{"username": "user", "password": "pass"}')
    def test_load_credentials(self, mock_file):
        creds = Scrapper.load_credentials()
        self.assertEqual(creds["username"], "user")
        self.assertEqual(creds["password"], "pass")

    def test_analyze_sentiment_basic(self):
        tweets = ["I love this!", "This is terrible.", "It's okay."]
        summary = Scrapper.analyze_sentiment(tweets)
        self.assertIn("Positive", summary)
        self.assertIn("Negative", summary)
        self.assertIn("Neutral", summary)

    def test_analyze_sentiment_empty(self):
        result = Scrapper.analyze_sentiment([])
        self.assertEqual(result, "❌ No tweets found.")
