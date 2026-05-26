import unittest

from network_lang import build_operation
from network_lang.adapters import (
    RouterOSExecutor,
    RouterOSRestTransport,
    plan_routeros_operation,
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


if __name__ == "__main__":
    unittest.main()
