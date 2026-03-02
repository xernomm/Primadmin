import unittest
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.prompt_templates import TOOL_PLANNING_TEMPLATE, VERIFICATION_TEMPLATE

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
            # Check if JSON structure is preserved
            self.assertIn('"name": "search_employees"', formatted)
            self.assertIn('"args":', formatted)
            self.assertIn('"{{step_1.result.id}}"', formatted)
            # Check completion_checklist is in the output
            self.assertIn("completion_checklist", formatted)
        except ValueError as e:
            self.fail(f"Formatting failed: {e}")
    
    def test_verification_template_formatting(self):
        """Verify VERIFICATION_TEMPLATE can be formatted without error."""
        try:
            formatted = VERIFICATION_TEMPLATE.format(
                original_query="test query",
                intent="test intent",
                tool_results="tool results here",
                retry_count=0
            )
            self.assertIn("test query", formatted)
            self.assertIn("test intent", formatted)
            # self.assertIn("item 1", formatted) # Removed as it's not in the template anymore
            self.assertIn("all_satisfied", formatted)
        except ValueError as e:
            self.fail(f"Formatting failed: {e}")

if __name__ == '__main__':
    unittest.main()

