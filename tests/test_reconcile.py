import unittest

from network_lang import DeviceRecord, reconcile_devices


class ReconcileTests(unittest.TestCase):
    def test_reports_unknown_live_and_missing_expected_devices(self):
        expected = [
            DeviceRecord(name="edge-01", host="192.168.88.1"),
            DeviceRecord(name="tower-ap-01", mac="AA-BB-CC-DD-EE-01"),
        ]
        observed = [
            DeviceRecord(name="edge-01-live", host="192.168.88.1"),
            DeviceRecord(name="unknown-cpe", host="10.20.30.45"),
        ]

        report = reconcile_devices(expected, observed)

        self.assertFalse(report.ok)
        self.assertEqual(len(report.matches), 1)
        self.assertEqual(report.matches[0].expected.name, "edge-01")
        self.assertEqual(report.matches[0].observed.name, "edge-01-live")
        self.assertEqual(report.matches[0].keys, ("host:192.168.88.1",))
        self.assertEqual(
            [device.label() for device in report.unknown_observed],
            ["unknown-cpe"],
        )
        self.assertEqual(
            [device.label() for device in report.missing_expected],
            ["tower-ap-01"],
        )

    def test_matches_mac_addresses_with_different_formats(self):
        expected = [DeviceRecord(name="cpe-01", mac="AA:BB:CC:DD:EE:FF")]
        observed = [DeviceRecord(host="10.0.0.2", mac="aabb.ccdd.eeff")]

        report = reconcile_devices(expected, observed)

        self.assertTrue(report.ok)
        self.assertEqual(report.matches[0].keys, ("mac:aa:bb:cc:dd:ee:ff",))

    def test_matches_custom_identifiers(self):
        expected = [
            DeviceRecord(
                name="customer-router",
                identifiers=("uisp:device/123",),
            )
        ]
        observed = [
            DeviceRecord(
                name="live-router",
                identifiers=("UISP:DEVICE/123",),
                source="uisp",
            )
        ]

        report = reconcile_devices(expected, observed)

        self.assertTrue(report.ok)
        self.assertEqual(report.matches[0].keys, ("uisp:device/123",))

    def test_accepts_dict_records_and_serials(self):
        report = reconcile_devices(
            [{"name": "router-01", "serial": "ABC123"}],
            [{"host": "192.0.2.1", "serial": "abc123"}],
        )

        self.assertTrue(report.ok)
        self.assertEqual(report.matches[0].keys, ("serial:abc123",))

    def test_report_serializes_to_dict(self):
        report = reconcile_devices(
            [DeviceRecord(name="known", host="192.0.2.1")],
            [DeviceRecord(name="unknown", host="192.0.2.2")],
        )

        data = report.to_dict()

        self.assertFalse(data["ok"])
        self.assertEqual(data["unknown_observed"][0]["name"], "unknown")
        self.assertEqual(data["missing_expected"][0]["name"], "known")


if __name__ == "__main__":
    unittest.main()
