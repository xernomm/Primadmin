
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from MCP.tools import email_tools

class TestEmailTools(unittest.TestCase):

    def test_sanitize_email(self):
        """Test email sanitization."""
        self.assertEqual(email_tools._sanitize_email(" test@example.com "), "test@example.com")
        self.assertEqual(email_tools._sanitize_email("'test@example.com'"), "test@example.com")
        self.assertEqual(email_tools._sanitize_email('"test@example.com"'), "test@example.com")
        self.assertEqual(email_tools._sanitize_email("test@example.com."), "test@example.com")
        self.assertEqual(email_tools._sanitize_email(""), "")
        self.assertEqual(email_tools._sanitize_email(None), "")

    @patch('MCP.tools.email_tools._get_connection')
    @patch('MCP.tools.email_tools.smtplib.SMTP')
    @patch('MCP.tools.email_tools._load_template')
    def test_send_warning_letter_success(self, mock_load_template, mock_smtp, mock_get_conn):
        """Test successful warning letter sending: commit should be called."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock fetchone responses
        # 1. Employee data
        mock_cursor.fetchone.side_effect = [
            (1, "Test Employee", "test@example.com", "EMP001", 0), # Employee
            ("HR Admin",), # Issuer
        ]
        
        # Mock template
        mock_load_template.return_value = "<html>Test Subject</html>"
        
        # Mock SMTP success (no exception)
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        
        # Execute
        result = email_tools.send_warning_letter(1, "Late")
        
        # Assertions
        self.assertTrue(result["success"])
        self.assertEqual(result["new_sp_level"], 1)
        
        # Verify transaction commit was called
        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()
        
        # Verify warnings update (email_sent=1) was executed
        updates = [call.args[0] for call in mock_cursor.execute.call_args_list]
        self.assertTrue(any("UPDATE warnings" in sql and "email_sent = 1" in sql for sql in updates))

    @patch('MCP.tools.email_tools._get_connection')
    @patch('MCP.tools.email_tools.smtplib.SMTP')
    @patch('MCP.tools.email_tools._load_template')
    def test_send_warning_letter_email_failure(self, mock_load_template, mock_smtp, mock_get_conn):
        """Test warning letter sending failure: rollback should be called."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock fetchone responses
        mock_cursor.fetchone.side_effect = [
            (1, "Test Employee", "test@example.com", "EMP001", 0), # Employee
            ("HR Admin",), # Issuer
        ]
        
        mock_load_template.return_value = "<html>Test Subject</html>"
        
        # Mock SMTP failure
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_smtp_instance
        mock_smtp_instance.sendmail.side_effect = Exception("SMTP Connection Failed")
        
        # Execute
        result = email_tools.send_warning_letter(1, "Late")
        
        # Assertions
        self.assertFalse(result["success"])
        self.assertIn("Gagal mengirim email", result["error"])
        
        # Verify transaction rollback was called
        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

if __name__ == '__main__':
    unittest.main()
