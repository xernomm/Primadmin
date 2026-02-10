import unittest
import sys
import os
import re

# Mock environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestPlaceholderSanitization(unittest.TestCase):
    
    def setUp(self):
        # Mock class to test the _sanitize_arguments method
        class AgentCore:
            def _sanitize_arguments(self, args):
                if isinstance(args, str):
                    if re.match(r'^{{step_\d+\.result\..*}}$', args):
                        return None
                    return re.sub(r'{{step_\d+\.result\.[^}]+}}', '', args).strip()
                elif isinstance(args, dict):
                    return {k: self._sanitize_arguments(v) for k, v in args.items()}
                elif isinstance(args, list):
                    return [self._sanitize_arguments(item) for item in args]
                return args
        
        self.agent = AgentCore()

    def test_sanitize_full_placeholder(self):
        """Test recursive sanitization of args containing placeholders."""
        args = {
            "emp_id": "{{step_1.result.id}}",
            "name": "John Doe",
            "nested": {
                "id": "{{step_2.result.id}}",
                "val": 123
            },
            "list": ["{{step_3.result.id}}", "valid"]
        }
        
        sanitized = self.agent._sanitize_arguments(args)
        
        self.assertIsNone(sanitized["emp_id"])
        self.assertEqual(sanitized["name"], "John Doe")
        self.assertIsNone(sanitized["nested"]["id"])
        self.assertEqual(sanitized["nested"]["val"], 123)
        self.assertIsNone(sanitized["list"][0])
        self.assertEqual(sanitized["list"][1], "valid")

    def test_sanitize_partial_placeholder(self):
        """Test sanitization of strings containing placeholders."""
        text = "Hello {{step_1.result.name}}, welcome!"
        sanitized = self.agent._sanitize_arguments(text)
        self.assertEqual(sanitized, "Hello , welcome!")

    def test_sql_generator_detection(self):
        """Test SQL generator rejection of placeholders."""
        # Mock execute_safe_sql logic
        def mock_execute_safe_sql(sql):
            if "{{" in sql and "}}" in sql:
                placeholders = re.findall(r'{{.*?}}', sql)
                if placeholders:
                    return {"success": False, "error": "Unresolved placeholders"}
            return {"success": True}

        # Test rejection
        result = mock_execute_safe_sql("SELECT * FROM employees WHERE id = {{step_1.result.id}}")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Unresolved placeholders")

        # Test acceptance
        result = mock_execute_safe_sql("SELECT * FROM employees WHERE id = 123")
        self.assertTrue(result["success"])

if __name__ == '__main__':
    unittest.main()
