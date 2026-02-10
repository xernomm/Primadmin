import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from MCP.tools.employee_tools import get_employee_by_id
from MCP.tools.email_tools import send_warning_letter

class TestFeatureUpdates(unittest.TestCase):
    
    @patch('MCP.tools.employee_tools._get_connection')
    def test_get_employee_details_query(self, mock_get_conn):
        """Test that get_employee_by_id queries for all new columns."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # Mock fetchone to return a row mirroring the columns
        # Columns: id, name, employee_code, position, address, status, basic_salary, 
        # phone, email, marital_status, department, remaining_leave, employment_status, 
        # sp_level, bpjs_number, joined_at, created_at, updated_at (18 columns)
        mock_cur.fetchone.return_value = tuple(range(18))
        mock_cur.description = [
            ('ID',), ('NAME',), ('EMPLOYEE_CODE',), ('POSITION',), ('ADDRESS',),
            ('STATUS',), ('BASIC_SALARY',), ('PHONE',), ('EMAIL',), ('MARITAL_STATUS',),
            ('DEPARTMENT',), ('REMAINING_LEAVE',), ('EMPLOYMENT_STATUS',), 
            ('SP_LEVEL',), ('BPJS_NUMBER',), ('JOINED_AT',), ('CREATED_AT',), ('UPDATED_AT',)
        ]
        
        result = get_employee_by_id(123)
        
        # Check if new columns are present in result
        self.assertTrue(result['success'])
        data = result['data']
        self.assertIn('SP_LEVEL', data)
        self.assertIn('BPJS_NUMBER', data)
        self.assertIn('CREATED_AT', data)
        
        # Verify SQL query contains new columns
        # We can inspect the call args
        args, _ = mock_cur.execute.call_args
        sql = args[0]
        self.assertIn('sp_level', sql.lower())
        self.assertIn('bpjs_number', sql.lower())
        self.assertIn('created_at', sql.lower())

    @patch('MCP.tools.email_tools._get_connection')
    def test_warning_letter_sp3_limit(self, mock_get_conn):
        """Test that send_warning_letter blocks if SP level is already 3."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # usage: id, name, email, employee_code, sp_level
        # Case 1: SP Level is 3
        mock_cur.fetchone.side_effect = [
            (1, "John Doe", "john@example.com", "EMP001", 3), # First fetch: employee data
            ("HR Admin",) # Second fetch: issuer name (if it gets there, which it shouldn't)
        ]
        
        result = send_warning_letter(1, "Late again")
        
        self.assertFalse(result['success'])
        self.assertIn("sudah mencapai level SP3", result['error'])
        self.assertIn("PHK", result['error'])
        
        # Case 2: SP Level is 2 (Should succeed and become SP3)
        mock_cur.reset_mock()
        mock_cur.fetchone.side_effect = [
            (1, "John Doe", "john@example.com", "EMP001", 2), # Employee data
            ("HR Admin",) # Issuer name
        ]
        # Mock template loading
        with patch('MCP.tools.email_tools._load_template', return_value="Template Content"):
            with patch('MCP.tools.email_tools._send_email', return_value=True):
                result = send_warning_letter(1, "Late again")
                self.assertTrue(result['success'])
                self.assertEqual(result['new_sp_level'], 3)
                self.assertEqual(result['sp_type'], "SP3")

if __name__ == '__main__':
    unittest.main()
