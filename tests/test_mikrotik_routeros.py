import unittest

from network_lang import build_operation
from network_lang.adapters import plan_routeros_operation


class RouterOSPlanTests(unittest.TestCase):
    def test_identity_get_maps_to_rest_path(self):
        operation = build_operation("network.system.identity.get", target="router-01")

        plan = plan_routeros_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.capability, "supported")
        self.assertEqual(plan.steps[0].method, "GET")
        self.assertEqual(plan.steps[0].path, "/system/identity")

    def test_route_create_translates_neutral_keys(self):
        operation = build_operation(
            "network.routes.create",
            target="router-01",
            route={
                "dst": "0.0.0.0/0",
                "gateway": "192.168.88.1",
                "table": "main",
            },
        )

        plan = plan_routeros_operation(operation)

        self.assertEqual(plan.steps[0].method, "PUT")
        self.assertEqual(plan.steps[0].path, "/ip/route")
        self.assertEqual(
            plan.steps[0].body,
            {
                "dst-address": "0.0.0.0/0",
                "gateway": "192.168.88.1",
                "routing-table": "main",
            },
        )

    def test_firewall_rule_create_translates_common_keys(self):
        operation = build_operation(
            "network.firewall.rules.create",
            target="router-01",
            rule={
                "chain": "forward",
                "action": "drop",
                "src": "10.20.30.0/24",
                "dst": "0.0.0.0/0",
            },
        )

        plan = plan_routeros_operation(operation)

        self.assertEqual(plan.steps[0].path, "/ip/firewall/filter")
        self.assertEqual(
            plan.steps[0].body,
            {
                "chain": "forward",
                "action": "drop",
                "src-address": "10.20.30.0/24",
                "dst-address": "0.0.0.0/0",
            },
        )

    def test_interface_disable_by_name_requires_lookup(self):
        operation = build_operation(
            "network.interfaces.disable",
            target="router-01",
            name="ether1",
        )

        plan = plan_routeros_operation(operation)

        self.assertEqual(plan.capability, "supported_via_fallback")
        self.assertEqual([step.method for step in plan.steps], ["GET", "PATCH"])
        self.assertEqual(plan.steps[0].params, {"name": "ether1"})
        self.assertEqual(plan.steps[1].body, {"disabled": True})

    def test_interface_enable_by_id_patches_directly(self):
        operation = build_operation(
            "network.interfaces.enable",
            target="router-01",
            id="*1",
        )

        plan = plan_routeros_operation(operation)

        self.assertEqual(plan.capability, "supported")
        self.assertEqual(plan.steps[0].method, "PATCH")
        self.assertEqual(plan.steps[0].path, "/interface/*1")
        self.assertEqual(plan.steps[0].body, {"disabled": False})

    def test_unknown_operation_is_unsupported(self):
        operation = build_operation("network.system.reboot.run", target="router-01")

        plan = plan_routeros_operation(operation)

        self.assertFalse(plan.supported)
        self.assertEqual(plan.capability, "unsupported")


if __name__ == "__main__":
    unittest.main()
