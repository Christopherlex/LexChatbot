import unittest
from unittest.mock import MagicMock, patch
import Main

class TestMainApp(unittest.TestCase):

    @patch("tkinter.Tk")
    def test_confirm_and_run_yes(self, mock_tk):
        app = Main.LexandChatApp(mock_tk)
        with patch("tkinter.messagebox.askyesno", return_value=True):
            func = MagicMock()
            app.append_bubble = MagicMock()
            app.root.after = MagicMock()
            app.confirm_and_run("Title", "Prompt?", func)
            app.root.after.assert_called()

    @patch("tkinter.Tk")
    def test_confirm_and_run_no(self, mock_tk):
        app = Main.LexandChatApp(mock_tk)
        with patch("tkinter.messagebox.askyesno", return_value=False):
            app.append_bubble = MagicMock()
            app.confirm_and_run("Sim", "Run?", lambda: None)
            app.append_bubble.assert_called_with("🤖", "Okay, I won’t run sim.", "left")

    @patch("tkinter.Tk")
    def test_send_message_quit(self, mock_tk):
        app = Main.LexandChatApp(mock_tk)
        app.user_input = MagicMock()
        app.user_input.get.return_value = "quit"
        app.user_input.delete = MagicMock()
        app.append_bubble = MagicMock()
        app.root = MagicMock()
        app.send_message()
        app.root.after.assert_called()

    @patch("tkinter.Tk")
    def test_ask_lmstudio_response(self, mock_tk):
        app = Main.LexandChatApp(mock_tk)
        app.append_bubble = MagicMock()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]

        with patch.object(Main.client.chat.completions, 'create', return_value=mock_response):
            app.ask_lmstudio("Hi")
            app.append_bubble.assert_called_with("🤖", "Test response", "left")

    @patch("tkinter.Tk")
    def test_run_scraper_gui_cancelled(self, mock_tk):
        app = Main.LexandChatApp(mock_tk)
        app.append_bubble = MagicMock()
        with patch("tkinter.simpledialog.askstring", return_value=None):
            app.run_scraper_gui()
            app.append_bubble.assert_called()

# python -m unittest discover -s tests -v
