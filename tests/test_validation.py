import unittest

from network_lang.parser import parse_text
from network_lang.validation import validate_operations


class ValidationTests(unittest.TestCase):
    def test_valid_operation_has_no_diagnostics(self):
        operations = parse_text('network.interfaces.get(target="core-sw-01", name="ether1")')

        self.assertEqual(validate_operations(operations), [])

    def test_unknown_action_is_error(self):
        operations = parse_text('network.interfaces.read(target="core-sw-01", name="ether1")')

        diagnostics = validate_operations(operations)

        self.assertEqual(diagnostics[0].level, "error")
        self.assertIn("unknown action 'read'", diagnostics[0].message)

    def test_target_is_required(self):
        operations = parse_text('network.interfaces.list(name="ether1")')

        diagnostics = validate_operations(operations)

        self.assertEqual(diagnostics[0].message, "operation must include target=...")


if __name__ == "__main__":
    unittest.main()

