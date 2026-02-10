import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from MCP.tools.email_tools import reset_sp_level, EMAIL_TOOLS
from agent.core import MAX_TOOL_ITERATIONS
from agent.prompt_templates import TOOL_PLANNING_TEMPLATE, SYSTEM_PROMPT

class TestToolImprovements(unittest.TestCase):
    
    @patch('MCP.tools.email_tools._get_connection')
    def test_reset_sp_level(self, mock_get_conn):
        """Test reset_sp_level tool logic."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # Mock employee exists
        mock_cur.fetchone.return_value = ("John Doe",)
        
        result = reset_sp_level(123, "Test Reset")
        
        self.assertTrue(result['success'])
        self.assertEqual(result['new_sp_level'], 0)
        self.assertIn("berhasil di-reset", result['message'])
        
        # Verify SQL calls
        # 1. Select name
        # 2. Update sp_level = 0
        # 3. Insert warning log
        self.assertEqual(mock_cur.execute.call_count, 3)
        
        # Check update query
        args_list = mock_cur.execute.call_args_list
        update_call = args_list[1]
        self.assertIn("UPDATE employees SET sp_level = 0", update_call[0][0])

    def test_send_warning_letter_description(self):
        """Verify send_warning_letter has explicit ACTION warning."""
        tool = next(t for t in EMAIL_TOOLS if t['name'] == 'send_warning_letter')
        description = tool['description']
        self.assertIn("ACTION TOOL", description)
        self.assertIn("JANGAN gunakan untuk sekadar mengecek", description)

    def test_max_tool_iterations(self):
        """Verify tool iteration limit received update."""
        self.assertEqual(MAX_TOOL_ITERATIONS, 50)

    def test_prompt_clarifications(self):
        """Verify prompts contain Read vs Write distinction."""
        self.assertIn("Bedakan tool untuk MENGECEK", TOOL_PLANNING_TEMPLATE)
        self.assertIn("Read Tools", SYSTEM_PROMPT)
        self.assertIn("Write Tools", SYSTEM_PROMPT)

if __name__ == '__main__':
    unittest.main()
