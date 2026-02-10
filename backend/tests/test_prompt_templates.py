import unittest
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.prompt_templates import TOOL_PLANNING_TEMPLATE

class TestPromptTemplates(unittest.TestCase):
    def test_tool_planning_template_formatting(self):
        """Verify TOOL_PLANNING_TEMPLATE can be formatted without error."""
        try:
            formatted = TOOL_PLANNING_TEMPLATE.format(
                intent="test intent",
                entities="{'name': 'test'}",
                expanded_query="expanded test",
                tool_descriptions="tool desc"
            )
            self.assertIn("test intent", formatted)
            self.assertIn("tool desc", formatted)
            # Check if JSON structure is preserved (single braces in output)
            self.assertIn('"arguments": {"emp_id": "{{step_1.result.id}}"}', formatted)
        except ValueError as e:
            self.fail(f"Formatting failed: {e}")

if __name__ == '__main__':
    unittest.main()
