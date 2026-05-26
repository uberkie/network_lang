import unittest

from network_lang import build_operation
from network_lang import AttachmentRecord, DeviceRecord, preflight_interface_operation
from network_lang.adapters import (
    RouterOSExecutor,
    RouterOSRestTransport,
    collect_routeros_topology,
    plan_routeros_operation,
    preflight_routeros_operation,
    routeros_arp_to_attachments,
    routeros_arp_to_devices,
    routeros_bridge_hosts_to_attachments,
    routeros_bridge_ports_to_interface_states,
    routeros_neighbors_to_attachments,
    routeros_neighbors_to_devices,
)


class FakeRouterOSTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, path, params=None, body=None):
        self.requests.append(
            {
                "method": method,
                "path": path,
                "params": params,
                "body": body,
            }
        )
        if not self.responses:
            return None
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.raised = False

    def raise_for_status(self):
        self.raised = True


class FakeRosSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params=None, verify=None):
        self.calls.append(("GET", url, params, None, verify))
        return self.response

    def put(self, url, json=None):
        self.calls.append(("PUT", url, None, json, None))
        return self.response

    def patch(self, url, json=None):
        self.calls.append(("PATCH", url, None, json, None))
        return self.response

    def post(self, url, json=None):
        self.calls.append(("POST", url, None, json, None))
        return self.response

    def delete(self, url):
        self.calls.append(("DELETE", url, None, None, None))
        return self.response


class FakeRos:
    def __init__(self, response):
        self.url = "https://router.example/rest"
        self.secure = False
        self.session = FakeRosSession(response)


class RouterOSPlanTests(unittest.TestCase):
    def test_identity_get_maps_to_rest_path(self):
        operation = build_operation("network.system.identity.get", target="router-01")

        plan = plan_routeros_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.capability, "supported")
        self.assertEqual(plan.steps[0].method, "GET")
        self.assertEqual(plan.steps[0].path, "/system/identity")

    def test_neighbors_list_maps_to_rest_path(self):
        operation = build_operation("network.neighbors.list", target="router-01")

        plan = plan_routeros_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.capability, "supported")
        self.assertEqual(plan.steps[0].method, "GET")
        self.assertEqual(plan.steps[0].path, "/ip/neighbor")

    def test_bridge_hosts_list_maps_to_rest_path(self):
        operation = build_operation("network.bridge.hosts.list", target="router-01")

        plan = plan_routeros_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.steps[0].method, "GET")
        self.assertEqual(plan.steps[0].path, "/interface/bridge/host")

    def test_bridge_ports_list_maps_to_rest_path(self):
        operation = build_operation("network.bridge.ports.list", target="router-01")

        plan = plan_routeros_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.steps[0].method, "GET")
        self.assertEqual(plan.steps[0].path, "/interface/bridge/port")

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


class RouterOSExecutorTests(unittest.TestCase):
    def test_executes_get_operation(self):
        operation = build_operation("network.system.identity.get", target="router-01")
        transport = FakeRouterOSTransport([{"name": "edge-01"}])

        result = RouterOSExecutor(transport).execute(operation)

        self.assertTrue(result.ok)
        self.assertEqual(result.operation, "network.system.identity.get")
        self.assertEqual(result.target, "router-01")
        self.assertEqual(result.adapter["vendor"], "mikrotik")
        self.assertEqual(result.data, {"name": "edge-01"})
        self.assertEqual(
            transport.requests,
            [
                {
                    "method": "GET",
                    "path": "/system/identity",
                    "params": None,
                    "body": None,
                }
            ],
        )

    def test_executes_route_create(self):
        operation = build_operation(
            "network.routes.create",
            target="router-01",
            route={"dst": "0.0.0.0/0", "gateway": "192.168.88.1"},
        )
        transport = FakeRouterOSTransport([{"id": "*1"}])

        result = RouterOSExecutor(transport).execute(operation)

        self.assertTrue(result.ok)
        self.assertEqual(result.data, {"id": "*1"})
        self.assertEqual(transport.requests[0]["method"], "PUT")
        self.assertEqual(transport.requests[0]["path"], "/ip/route")
        self.assertEqual(
            transport.requests[0]["body"],
            {"dst-address": "0.0.0.0/0", "gateway": "192.168.88.1"},
        )

    def test_resolves_id_before_interface_disable(self):
        operation = build_operation(
            "network.interfaces.disable",
            target="router-01",
            name="ether1",
        )
        transport = FakeRouterOSTransport(
            [
                [{"id": "*2", "name": "ether1"}],
                {"id": "*2", "disabled": True},
            ]
        )

        result = RouterOSExecutor(transport).execute(operation)

        self.assertTrue(result.ok)
        self.assertEqual(result.data, {"id": "*2", "disabled": True})
        self.assertEqual(
            transport.requests,
            [
                {
                    "method": "GET",
                    "path": "/interface",
                    "params": {"name": "ether1"},
                    "body": None,
                },
                {
                    "method": "PATCH",
                    "path": "/interface/*2",
                    "params": None,
                    "body": {"disabled": True},
                },
            ],
        )

    def test_lookup_not_found_returns_error_result(self):
        operation = build_operation(
            "network.interfaces.disable",
            target="router-01",
            name="ether99",
        )
        transport = FakeRouterOSTransport([[]])

        result = RouterOSExecutor(transport).execute(operation)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "LOOKUP_NOT_FOUND")
        self.assertEqual(len(transport.requests), 1)

    def test_unsupported_operation_returns_error_without_transport_call(self):
        operation = build_operation("network.system.reboot.run", target="router-01")
        transport = FakeRouterOSTransport([])

        result = RouterOSExecutor(transport).execute(operation)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "UNSUPPORTED_OPERATION")
        self.assertEqual(transport.requests, [])


class RouterOSTopologyCollectionTests(unittest.TestCase):
    def test_collect_routeros_topology_reads_neighbors_and_bridge_ports(self):
        transport = FakeRouterOSTransport(
            [
                [
                    {
                        "address4": "192.168.0.10",
                        "identity": "tower-cpe-01",
                        "interface_name": "bridge1/ether2",
                        "mac_address": "74:4D:28:35:62:1B",
                    }
                ],
                [
                    {
                        "interface": "ether2",
                        "bridge": "bridge1",
                        "disabled": "false",
                        "inactive": "true",
                        "status": "inactive",
                    }
                ],
            ]
        )

        result = collect_routeros_topology(RouterOSExecutor(transport), "edge-01")

        self.assertTrue(result.ok)
        self.assertEqual(result.operation, "network.topology.snapshot.observe")
        self.assertEqual(result.data.attachments[0].interface, "ether2")
        self.assertEqual(result.data.interface_states[0].interface, "ether2")
        self.assertTrue(result.data.interface_states[0].inactive)
        self.assertFalse(result.data.interface_states[0].running)
        self.assertEqual(
            [request["path"] for request in transport.requests],
            ["/ip/neighbor", "/interface/bridge/port"],
        )
        self.assertEqual(
            result.to_dict()["data"]["interface_states"][0]["status"],
            "inactive",
        )

    def test_preflight_routeros_operation_uses_live_interface_state(self):
        transport = FakeRouterOSTransport(
            [
                [],
                [
                    {
                        "interface": "ether2",
                        "bridge": "bridge1",
                        "disabled": "false",
                        "inactive": "true",
                        "status": "inactive",
                    }
                ],
            ]
        )
        operation = build_operation(
            "network.interfaces.disable",
            target="edge-01",
            name="ether2",
        )

        result = preflight_routeros_operation(RouterOSExecutor(transport), operation)

        self.assertFalse(result.ok)
        self.assertEqual(result.capability, "preflight")
        self.assertEqual(result.error.code, "PREFLIGHT_RISK")
        self.assertEqual(
            result.data.risks,
            ("edge-01 ether2 (bridge1) is inactive",),
        )

    def test_preflight_routeros_operation_accepts_network_device_alias(self):
        transport = FakeRouterOSTransport(
            [
                [],
                [
                    {
                        "interface": "ether2",
                        "bridge": "bridge1",
                        "inactive": "true",
                        "status": "inactive",
                    }
                ],
            ]
        )
        operation = build_operation(
            "network.interfaces.disable",
            target="router-01",
            name="ether2",
        )

        result = preflight_routeros_operation(
            RouterOSExecutor(transport),
            operation,
            network_device="edge-01",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.target, "router-01")
        self.assertEqual(result.data.target, "edge-01")
        self.assertEqual(
            result.data.risks,
            ("edge-01 ether2 (bridge1) is inactive",),
        )


class RouterOSRestTransportTests(unittest.TestCase):
    def test_rest_transport_uses_ros_session_and_cleans_response_keys(self):
        response = FakeResponse(
            '[{".id": "*1", "dst-address": "0.0.0.0/0", "routing-table": "main"}]'
        )
        ros = FakeRos(response)

        data = RouterOSRestTransport(ros).request(
            "GET",
            "/ip/route",
            params={"dst-address": "0.0.0.0/0"},
        )

        self.assertTrue(response.raised)
        self.assertEqual(
            ros.session.calls,
            [
                (
                    "GET",
                    "https://router.example/rest/ip/route",
                    {"dst-address": "0.0.0.0/0"},
                    None,
                    False,
                )
            ],
        )
        self.assertEqual(
            data,
            [{"id": "*1", "dst_address": "0.0.0.0/0", "routing_table": "main"}],
        )


class RouterOSNormalizerTests(unittest.TestCase):
    def test_neighbor_rows_become_device_records(self):
        row = {
            "id": "*2",
            "address": "192.168.0.10",
            "address4": "192.168.0.10",
            "board": "RB941-2nD",
            "discovered_by": "mndp",
            "identity": "tower-cpe-01",
            "interface": "wlan2",
            "interface_name": "bridge1/ether2",
            "mac_address": "74:4D:28:35:62:1B",
            "platform": "MikroTik",
            "software_id": "F1BY-SY6F",
            "version": "6.49.19 (stable)",
        }

        devices = routeros_neighbors_to_devices([row])

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].name, "tower-cpe-01")
        self.assertEqual(devices[0].host, "192.168.0.10")
        self.assertEqual(devices[0].mac, "74:4D:28:35:62:1B")
        self.assertEqual(devices[0].serial, "F1BY-SY6F")
        self.assertEqual(devices[0].vendor, "MikroTik")
        self.assertIn("routeros:mndp/identity/tower-cpe-01", devices[0].identifiers)

    def test_neighbor_rows_become_attachment_records(self):
        row = {
            "address4": "192.168.0.10",
            "identity": "tower-cpe-01",
            "interface": "wlan2",
            "interface_name": "bridge1/ether2",
            "mac_address": "74:4D:28:35:62:1B",
        }

        attachments = routeros_neighbors_to_attachments([row], "router-01")

        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].network_device, "router-01")
        self.assertEqual(attachments[0].interface, "ether2")
        self.assertEqual(attachments[0].source, "routeros:/ip/neighbor")
        self.assertEqual(attachments[0].device.name, "tower-cpe-01")

    def test_neighbor_rows_normalize_bridge_member_interface_pairs(self):
        row = {
            "interface": "ether4,bridge1",
            "mac_address": "2C:F0:5D:DD:59:65",
        }

        attachments = routeros_neighbors_to_attachments([row], "router-01")

        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].interface, "ether4")
        self.assertEqual(attachments[0].metadata["interface"], "ether4,bridge1")

    def test_arp_rows_become_device_and_attachment_records(self):
        row = {
            "address": "10.20.30.45",
            "mac_address": "AA:BB:CC:DD:EE:01",
            "interface": "bridge-customers",
            "dynamic": "true",
        }

        devices = routeros_arp_to_devices([row])
        attachments = routeros_arp_to_attachments([row], "tower-router-03")

        self.assertEqual(devices[0].host, "10.20.30.45")
        self.assertEqual(devices[0].mac, "AA:BB:CC:DD:EE:01")
        self.assertEqual(attachments[0].network_device, "tower-router-03")
        self.assertEqual(attachments[0].interface, "bridge-customers")
        self.assertEqual(attachments[0].source, "routeros:/ip/arp")

    def test_bridge_host_rows_become_attachment_records(self):
        row = {
            "mac_address": "AA:BB:CC:DD:EE:01",
            "interface": "ether4",
            "bridge": "bridge1",
            "vid": "10",
        }

        attachments = routeros_bridge_hosts_to_attachments([row], "poe-switch-01")

        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].device.mac, "AA:BB:CC:DD:EE:01")
        self.assertEqual(attachments[0].interface, "ether4")
        self.assertEqual(attachments[0].metadata["vid"], "10")

    def test_bridge_port_rows_become_interface_state_records(self):
        row = {
            "id": "*1",
            "interface": "ether2",
            "bridge": "bridge1",
            "disabled": "false",
            "inactive": "true",
            "status": "inactive",
            "hw": "yes",
        }

        states = routeros_bridge_ports_to_interface_states([row], "poe-switch-01")

        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].network_device, "poe-switch-01")
        self.assertEqual(states[0].interface, "ether2")
        self.assertEqual(states[0].scope, "bridge1")
        self.assertFalse(states[0].disabled)
        self.assertTrue(states[0].inactive)
        self.assertFalse(states[0].running)
        self.assertEqual(states[0].status, "inactive")
        self.assertEqual(states[0].source, "routeros:/interface/bridge/port")

    def test_bridge_port_running_can_be_derived_from_status(self):
        row = {
            "interface": "wlan3",
            "bridge": "bridge1",
            "disabled": "false",
            "status": "in-bridge",
            "forwarding": "true",
        }

        states = routeros_bridge_ports_to_interface_states([row], "poe-switch-01")

        self.assertFalse(states[0].inactive)
        self.assertTrue(states[0].running)
        self.assertEqual(states[0].status, "in-bridge")
        self.assertTrue(states[0].forwarding)

    def test_routeros_attachments_feed_preflight(self):
        operation = build_operation(
            "network.interfaces.disable",
            target="poe-switch-01",
            name="ether1",
        )
        expected = [
            AttachmentRecord(
                device=DeviceRecord(name="device1", mac="AA:BB:CC:DD:EE:01"),
                network_device="poe-switch-01",
                interface="ether1",
            )
        ]
        observed = routeros_bridge_hosts_to_attachments(
            [
                {
                    "mac_address": "AA:BB:CC:DD:EE:01",
                    "interface": "ether4",
                }
            ],
            "poe-switch-01",
        )

        report = preflight_interface_operation(operation, expected, observed)

        self.assertFalse(report.ok)
        self.assertIn("device1 expected on poe-switch-01 ether1", report.risks[0])
        self.assertIn("but observed on poe-switch-01 ether4", report.risks[0])


if __name__ == "__main__":
    unittest.main()
