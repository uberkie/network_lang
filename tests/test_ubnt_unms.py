import unittest

from network_lang import build_operation
from network_lang.adapters import (
    UNMSEndpoints,
    UNMSExecutor,
    UNMSRestTransport,
    plan_unms_operation,
)


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.raised = False

    def raise_for_status(self):
        self.raised = True


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append(
            {
                "method": method,
                "url": url,
                "kwargs": kwargs,
            }
        )
        return self.response


class FakeUNMSTransport:
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


class UNMSEndpointTests(unittest.TestCase):
    def test_builds_api_url_from_controller_url(self):
        endpoints = UNMSEndpoints.from_url("https://uisp.example.com/nms/")

        self.assertEqual(endpoints.base_url, "https://uisp.example.com/nms")
        self.assertEqual(endpoints.api_url, "https://uisp.example.com/nms/api/v2.1/")
        self.assertEqual(
            endpoints.resource_url("/devices"),
            "https://uisp.example.com/nms/api/v2.1/devices",
        )

    def test_converts_legacy_crm_path_to_nms_path(self):
        endpoints = UNMSEndpoints.from_url("https://uisp.example.com/crm/")

        self.assertEqual(endpoints.api_url, "https://uisp.example.com/nms/api/v2.1/")

    def test_rejects_empty_url(self):
        with self.assertRaises(ValueError):
            UNMSEndpoints.from_url("")


class UNMSTransportTests(unittest.TestCase):
    def test_sends_x_auth_token_and_decodes_json(self):
        response = FakeResponse('[{"id": "abc"}]')
        session = FakeSession(response)
        transport = UNMSRestTransport(
            UNMSEndpoints.from_url("https://uisp.example.com/nms"),
            "secret-token",
            session=session,
            verify=False,
            timeout=10,
        )

        result = transport.request("GET", "/devices", params={"site": "main"})

        self.assertEqual(result, [{"id": "abc"}])
        self.assertTrue(response.raised)
        request = session.requests[0]
        self.assertEqual(request["method"], "GET")
        self.assertEqual(
            request["url"],
            "https://uisp.example.com/nms/api/v2.1/devices",
        )
        self.assertEqual(
            request["kwargs"]["headers"],
            {"x-auth-token": "secret-token"},
        )
        self.assertEqual(request["kwargs"]["params"], {"site": "main"})
        self.assertFalse(request["kwargs"]["verify"])
        self.assertEqual(request["kwargs"]["timeout"], 10)


class UNMSPlanTests(unittest.TestCase):
    def test_devices_list_maps_to_controller_devices_path(self):
        operation = build_operation(
            "network.controller.devices.list",
            target="uisp",
            match={"site_id": "site-1"},
        )

        plan = plan_unms_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.steps[0].method, "GET")
        self.assertEqual(plan.steps[0].path, "/devices")
        self.assertEqual(plan.steps[0].params, {"site-id": "site-1"})

    def test_device_get_by_id_maps_to_resource_path(self):
        operation = build_operation(
            "network.controller.devices.get",
            target="uisp",
            id="device-1",
        )

        plan = plan_unms_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.steps[0].path, "/devices/device-1")

    def test_controller_endpoint_can_be_given_as_param(self):
        operation = build_operation(
            "network.unms.list",
            target="uisp",
            endpoint="devices/firmwares",
        )

        plan = plan_unms_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.steps[0].path, "/devices/firmwares")

    def test_create_update_and_delete_map_to_write_methods(self):
        create = plan_unms_operation(
            build_operation(
                "network.controller.sites.create",
                target="uisp",
                data={"name": "Tower A"},
            )
        )
        update = plan_unms_operation(
            build_operation(
                "network.controller.sites.update",
                target="uisp",
                id="site-1",
                data={"name": "Tower B"},
            )
        )
        delete = plan_unms_operation(
            build_operation(
                "network.controller.sites.delete",
                target="uisp",
                id="site-1",
            )
        )

        self.assertEqual(create.steps[0].method, "POST")
        self.assertEqual(create.steps[0].path, "/sites")
        self.assertEqual(create.steps[0].body, {"name": "Tower A"})
        self.assertEqual(update.steps[0].method, "PATCH")
        self.assertEqual(update.steps[0].path, "/sites/site-1")
        self.assertEqual(delete.steps[0].method, "DELETE")
        self.assertIn("delete is destructive", delete.warnings[0])

    def test_unknown_operation_is_unsupported(self):
        operation = build_operation("network.devices.list", target="uisp")

        plan = plan_unms_operation(operation)

        self.assertFalse(plan.supported)
        self.assertEqual(plan.capability, "unsupported")


class UNMSExecutorTests(unittest.TestCase):
    def test_executor_runs_plan_and_wraps_result(self):
        transport = FakeUNMSTransport([[{"id": "device-1"}]])
        executor = UNMSExecutor(transport)
        operation = build_operation("network.controller.devices.list", target="uisp")

        result = executor.execute(operation)

        self.assertTrue(result.ok)
        self.assertEqual(result.adapter["name"], "unms-rest")
        self.assertEqual(result.data, [{"id": "device-1"}])
        self.assertEqual(transport.requests[0]["method"], "GET")
        self.assertEqual(transport.requests[0]["path"], "/devices")

    def test_executor_returns_adapter_error(self):
        transport = FakeUNMSTransport([RuntimeError("boom")])
        executor = UNMSExecutor(transport)
        operation = build_operation("network.controller.devices.list", target="uisp")

        result = executor.execute(operation)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "ADAPTER_ERROR")
        self.assertIn("boom", result.error.message)


if __name__ == "__main__":
    unittest.main()
