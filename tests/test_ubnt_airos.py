import unittest

from network_lang import build_operation
from network_lang.adapters import AirOSEndpoints, plan_airos_operation


class AirOSEndpointTests(unittest.TestCase):
    def test_builds_known_endpoint_urls(self):
        endpoints = AirOSEndpoints.from_host("192.168.0.20")

        self.assertEqual(endpoints.base_url, "https://192.168.0.20")
        self.assertEqual(endpoints.login_url, "https://192.168.0.20/api/auth")
        self.assertEqual(endpoints.status_cgi_url, "https://192.168.0.20/status.cgi")
        self.assertEqual(endpoints.reboot_cgi_url, "https://192.168.0.20/reboot.cgi")
        self.assertEqual(endpoints.v6_xm_login_url, "https://192.168.0.20/login.cgi")
        self.assertEqual(endpoints.v6_form_url, "/index.cgi")
        self.assertEqual(endpoints.stakick_cgi_url, "https://192.168.0.20/stakick.cgi")
        self.assertEqual(endpoints.provmode_url, "https://192.168.0.20/api/provmode")
        self.assertEqual(endpoints.warnings_url, "https://192.168.0.20/api/warnings")
        self.assertEqual(
            endpoints.update_check_url,
            "https://192.168.0.20/api/fw/update-check",
        )
        self.assertEqual(endpoints.download_url, "https://192.168.0.20/api/fw/download")
        self.assertEqual(
            endpoints.download_progress_url,
            "https://192.168.0.20/api/fw/download-progress",
        )
        self.assertEqual(endpoints.install_url, "https://192.168.0.20/fwflash.cgi")
        self.assertEqual(
            endpoints.login_urls,
            (
                "https://192.168.0.20/api/auth",
                "https://192.168.0.20/login.cgi",
            ),
        )

    def test_rejects_empty_host(self):
        with self.assertRaises(ValueError):
            AirOSEndpoints.from_host("")


class AirOSPlanTests(unittest.TestCase):
    def test_status_operation_supports_v8_and_v6_login_paths(self):
        endpoints = AirOSEndpoints.from_host("192.168.0.20")
        operation = build_operation("network.wireless.clients.list", target="cpe-01")

        plan = plan_airos_operation(operation, endpoints)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.capability, "supported")
        self.assertEqual(
            [step.name for step in plan.steps],
            ["login_v8", "login_v6_fallback", "status"],
        )
        self.assertEqual(plan.steps[-1].url, "https://192.168.0.20/status.cgi")

    def test_v6_status_is_marked_as_fallback(self):
        endpoints = AirOSEndpoints.from_host("192.168.0.20")
        operation = build_operation("network.system.status.get", target="cpe-01")

        plan = plan_airos_operation(operation, endpoints, firmware_major=6)

        self.assertEqual(plan.capability, "supported_via_fallback")
        self.assertIn("airOS 6 status uses legacy login flow", plan.warnings)

    def test_station_kick_requires_mac_match(self):
        endpoints = AirOSEndpoints.from_host("192.168.0.20")
        operation = build_operation("network.wireless.clients.delete", target="cpe-01")

        plan = plan_airos_operation(operation, endpoints)

        self.assertFalse(plan.supported)
        self.assertEqual(plan.capability, "unsupported")
        self.assertIn("wireless client delete requires match.mac", plan.warnings)

    def test_station_kick_maps_to_stakick(self):
        endpoints = AirOSEndpoints.from_host("192.168.0.20")
        operation = build_operation(
            "network.wireless.clients.delete",
            target="cpe-01",
            match={"mac": "01:23:45:67:89:AB"},
        )

        plan = plan_airos_operation(operation, endpoints)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.steps[1].method, "POST")
        self.assertEqual(plan.steps[1].url, "https://192.168.0.20/stakick.cgi")
        self.assertEqual(plan.steps[1].body, {"sta": "01:23:45:67:89:AB"})

    def test_unknown_operation_is_unsupported(self):
        endpoints = AirOSEndpoints.from_host("192.168.0.20")
        operation = build_operation("network.routes.create", target="cpe-01")

        plan = plan_airos_operation(operation, endpoints)

        self.assertEqual(plan.capability, "unsupported")
        self.assertEqual(plan.steps, ())


if __name__ == "__main__":
    unittest.main()
