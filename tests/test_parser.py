import unittest
from pathlib import Path

from network_lang import build_operation, network, validate_operation
from network_lang.parser import ParseError, parse_file, parse_text


class ParserTests(unittest.TestCase):
    def test_parses_example_file(self):
        operations = parse_file(Path("examples/operations.uns"))

        self.assertEqual(len(operations), 10)
        self.assertEqual(operations[0].name, "network.neighbors.list")
        self.assertEqual(operations[0].target, "tower-router-01")
        self.assertEqual(operations[7].params["rule"]["src"], "10.20.30.0/24")

    def test_parses_nested_values(self):
        operations = parse_text(
            """
            network.firewall.rules.create(
              target="edge-01",
              rule={
                chain="forward",
                ports=[80, 443],
                enabled=true,
                note=null
              }
            )
            """
        )

        self.assertEqual(operations[0].resource_path, ("firewall", "rules"))
        self.assertEqual(operations[0].params["rule"]["ports"], [80, 443])
        self.assertTrue(operations[0].params["rule"]["enabled"])
        self.assertIsNone(operations[0].params["rule"]["note"])

    def test_comments_do_not_break_strings(self):
        operations = parse_text(
            'network.system.identity.get(target="ap#1") # trailing comment\n'
        )

        self.assertEqual(operations[0].target, "ap#1")

    def test_rejects_malformed_call(self):
        with self.assertRaises(ParseError):
            parse_text("network.interfaces.get target=\"core-sw-01\"")


class LibraryApiTests(unittest.TestCase):
    def test_fluent_builder_creates_operation(self):
        operation = network.interfaces.get(target="core-sw-01", name="ether1")

        self.assertEqual(operation.name, "network.interfaces.get")
        self.assertEqual(operation.resource_path, ("interfaces",))
        self.assertEqual(operation.action, "get")
        self.assertEqual(operation.params["name"], "ether1")
        self.assertEqual(validate_operation(operation), [])

    def test_fluent_builder_supports_nested_resources(self):
        operation = network.system.identity.get(target="ap-south-03")

        self.assertEqual(operation.name, "network.system.identity.get")
        self.assertEqual(operation.resource_path, ("system", "identity"))

    def test_fluent_builder_requires_resource_and_action(self):
        with self.assertRaises(ValueError):
            network.interfaces(target="core-sw-01")

    def test_build_operation_from_dotted_name(self):
        operation = build_operation(
            "network.firewall.rules.create",
            target="edge-01",
            rule={"action": "drop"},
        )

        self.assertEqual(operation.name, "network.firewall.rules.create")
        self.assertEqual(operation.resource_path, ("firewall", "rules"))

    def test_build_operation_rejects_bad_name(self):
        with self.assertRaises(ValueError):
            build_operation("network.interfaces")


if __name__ == "__main__":
    unittest.main()
