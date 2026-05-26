import unittest

from network_lang import (
    TargetDevice,
    TargetResolutionError,
    collect_topology,
    load_inventory,
    resolve_target,
    target_device,
)
from network_lang.result import OperationResult
from network_lang.adapters import RouterOSExecutor


class FakeExecutor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.operations = []

    def execute(self, operation):
        self.operations.append(operation)
        return self.responses.pop(0)


class TargetResolutionTests(unittest.TestCase):
    def test_resolve_target_matches_name(self):
        record = resolve_target(
            "edge-01",
            inventory=[
                {
                    "name": "edge-01",
                    "url": "https://192.0.2.1/",
                }
            ],
        )

        self.assertEqual(record["url"], "https://192.0.2.1/")

    def test_resolve_target_matches_url(self):
        record = resolve_target(
            "https://192.0.2.1/",
            inventory=[
                {
                    "name": "edge-01",
                    "url": "https://192.0.2.1/",
                }
            ],
        )

        self.assertEqual(record["name"], "edge-01")

    def test_missing_target_raises_resolution_error(self):
        with self.assertRaisesRegex(TargetResolutionError, "not found"):
            resolve_target("missing", inventory=[])

    def test_target_device_builds_routeros_execution_context(self):
        device = target_device(
            "edge-01",
            inventory=[
                {
                    "name": "edge-01",
                    "url": "https://192.0.2.1/",
                    "username": "admin",
                    "password": "password",
                }
            ],
        )

        self.assertIsInstance(device, TargetDevice)
        self.assertIsInstance(device.executor, RouterOSExecutor)
        self.assertEqual(device.name, "edge-01")
        self.assertEqual(device.network_device, "edge-01")
        self.assertEqual(device.url, "https://192.0.2.1/")
        self.assertEqual(device.vendor, "mikrotik")
        self.assertEqual(device.platform, "routeros")

    def test_target_device_builds_targeted_operation(self):
        device = TargetDevice(
            name="edge-01",
            url="https://192.0.2.1/",
            vendor="mikrotik",
            platform="routeros",
            transport="rest",
            executor=FakeExecutor([]),
        )

        operation = device.operation("network.interfaces.disable", name="ether2")

        self.assertEqual(operation.name, "network.interfaces.disable")
        self.assertEqual(operation.target, "edge-01")
        self.assertEqual(operation.params["name"], "ether2")

    def test_collect_topology_dispatches_through_target_device(self):
        executor = FakeExecutor(
            [
                OperationResult(
                    ok=True,
                    operation="network.neighbors.list",
                    target="edge-01",
                    capability="supported",
                    adapter=None,
                    data=[
                        {
                            "identity": "cpe-01",
                            "interface_name": "bridge1/ether2",
                            "mac_address": "AA:BB:CC:DD:EE:01",
                        }
                    ],
                ),
                OperationResult(
                    ok=True,
                    operation="network.bridge.ports.list",
                    target="edge-01",
                    capability="supported",
                    adapter=None,
                    data=[
                        {
                            "interface": "ether2",
                            "bridge": "bridge1",
                            "inactive": "true",
                            "status": "inactive",
                        }
                    ],
                ),
            ]
        )
        device = TargetDevice(
            name="edge-01",
            url="https://192.0.2.1/",
            vendor="mikrotik",
            platform="routeros",
            transport="rest",
            executor=executor,
        )

        result = collect_topology(device)

        self.assertTrue(result.ok)
        self.assertEqual(result.data.attachments[0].interface, "ether2")
        self.assertEqual(result.data.interface_states[0].status, "inactive")

    def test_target_device_preflight_hides_adapter_specific_calls(self):
        executor = FakeExecutor(
            [
                OperationResult(
                    ok=True,
                    operation="network.neighbors.list",
                    target="edge-01",
                    capability="supported",
                    adapter=None,
                    data=[],
                ),
                OperationResult(
                    ok=True,
                    operation="network.bridge.ports.list",
                    target="edge-01",
                    capability="supported",
                    adapter=None,
                    data=[
                        {
                            "interface": "ether2",
                            "bridge": "bridge1",
                            "inactive": "true",
                            "status": "inactive",
                        }
                    ],
                ),
            ]
        )
        device = TargetDevice(
            name="edge-01",
            url="https://192.0.2.1/",
            vendor="mikrotik",
            platform="routeros",
            transport="rest",
            executor=executor,
        )

        result = device.preflight("network.interfaces.disable", name="ether2")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "PREFLIGHT_RISK")
        self.assertEqual(
            result.data.risks,
            ("edge-01 ether2 (bridge1) is inactive",),
        )

    def test_target_device_rejects_record_without_url(self):
        with self.assertRaisesRegex(TargetResolutionError, "does not have a URL"):
            target_device("edge-01", inventory=[{"name": "edge-01"}])

    def test_load_inventory_requires_list(self):
        with self.assertRaisesRegex(TargetResolutionError, "must contain a list"):
            load_inventory("tests/fixtures/not-a-list.json")


if __name__ == "__main__":
    unittest.main()
