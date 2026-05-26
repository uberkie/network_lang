import unittest

from network_lang import (
    AttachmentRecord,
    DeviceRecord,
    InterfaceStateRecord,
    build_operation,
    preflight_interface_operation,
    reconcile_attachments,
)


class TopologyAttachmentTests(unittest.TestCase):
    def test_reconcile_attachments_reports_moved_unknown_and_missing(self):
        expected = [
            _attachment("device1", "AA:BB:CC:DD:EE:01", "poe-switch-01", "ether1"),
            _attachment("device2", "AA:BB:CC:DD:EE:02", "poe-switch-01", "ether1"),
            _attachment("device3", "AA:BB:CC:DD:EE:03", "poe-switch-01", "ether1"),
        ]
        observed = [
            _attachment("device1-live", "AA-BB-CC-DD-EE-01", "poe-switch-01", "ether1"),
            _attachment("device2-live", "AA-BB-CC-DD-EE-02", "poe-switch-01", "ether4"),
            _attachment("unknown", "AA-BB-CC-DD-EE-99", "poe-switch-01", "ether1"),
        ]

        report = reconcile_attachments(expected, observed)

        self.assertFalse(report.ok)
        self.assertEqual(report.matches[0].expected.device.name, "device1")
        self.assertEqual(report.moved[0].expected.device.name, "device2")
        self.assertEqual(report.moved[0].observed.interface, "ether4")
        self.assertEqual(report.unknown_observed[0].device.name, "unknown")
        self.assertEqual(report.missing_expected[0].device.name, "device3")

    def test_duplicate_observed_flags_same_identity_on_multiple_ports(self):
        observed = [
            _attachment("device1-a", "AA:BB:CC:DD:EE:01", "poe-switch-01", "ether1"),
            _attachment("device1-b", "AA:BB:CC:DD:EE:01", "poe-switch-01", "ether4"),
        ]

        report = reconcile_attachments([], observed)

        self.assertFalse(report.ok)
        self.assertEqual(report.duplicate_observed[0].key, "mac:aa:bb:cc:dd:ee:01")
        self.assertEqual(
            [record.interface for record in report.duplicate_observed[0].observations],
            ["ether1", "ether4"],
        )

    def test_preflight_interface_operation_scopes_to_target_port(self):
        operation = build_operation(
            "network.interfaces.disable",
            target="poe-switch-01",
            name="ether1",
        )
        expected = [
            _attachment("device1", "AA:BB:CC:DD:EE:01", "poe-switch-01", "ether1"),
            _attachment("device2", "AA:BB:CC:DD:EE:02", "poe-switch-01", "ether1"),
            _attachment("other-port", "AA:BB:CC:DD:EE:03", "poe-switch-01", "ether8"),
        ]
        observed = [
            _attachment("device1-live", "AA-BB-CC-DD-EE-01", "poe-switch-01", "ether1"),
            _attachment("device2-live", "AA-BB-CC-DD-EE-02", "poe-switch-01", "ether4"),
            _attachment("unknown", "AA-BB-CC-DD-EE-99", "poe-switch-01", "ether1"),
            _attachment("other-port", "AA-BB-CC-DD-EE-03", "poe-switch-01", "ether8"),
        ]

        report = preflight_interface_operation(operation, expected, observed)

        self.assertFalse(report.ok)
        self.assertEqual(report.interface, "ether1")
        self.assertEqual(len(report.reconciliation.matches), 1)
        self.assertEqual(len(report.reconciliation.moved), 1)
        self.assertEqual(len(report.reconciliation.unknown_observed), 1)
        self.assertEqual(len(report.reconciliation.missing_expected), 0)
        self.assertEqual(len(report.risks), 2)
        self.assertIn("device2 expected on poe-switch-01 ether1", report.risks[0])
        self.assertIn("unknown live device unknown", report.risks[1])

    def test_preflight_requires_target_interface(self):
        operation = build_operation("network.interfaces.disable", target="poe-switch-01")

        report = preflight_interface_operation(operation, [], [])

        self.assertFalse(report.ok)
        self.assertEqual(
            report.risks,
            ("operation does not identify a target interface",),
        )

    def test_preflight_ok_when_expected_matches_live(self):
        operation = build_operation(
            "network.interfaces.disable",
            target="poe-switch-01",
            name="ether1",
        )
        expected = [
            _attachment("device1", "AA:BB:CC:DD:EE:01", "poe-switch-01", "ether1"),
        ]
        observed = [
            _attachment("device1-live", "AA-BB-CC-DD-EE-01", "poe-switch-01", "ether1"),
        ]

        report = preflight_interface_operation(operation, expected, observed)

        self.assertTrue(report.ok)
        self.assertEqual(report.risks, ())

    def test_preflight_flags_inactive_interface_state(self):
        operation = build_operation(
            "network.interfaces.disable",
            target="poe-switch-01",
            name="ether2",
        )
        interface_states = [
            InterfaceStateRecord(
                network_device="poe-switch-01",
                interface="ether2",
                scope="bridge1",
                inactive=True,
            )
        ]

        report = preflight_interface_operation(
            operation,
            [],
            [],
            interface_states,
        )

        self.assertFalse(report.ok)
        self.assertEqual(report.interface_state, interface_states[0])
        self.assertEqual(report.risks, ("poe-switch-01 ether2 (bridge1) is inactive",))

    def test_accepts_dict_attachment_records(self):
        report = reconcile_attachments(
            [
                {
                    "device": {"name": "device1", "mac": "AA:BB:CC:DD:EE:01"},
                    "network_device": "poe-switch-01",
                    "interface": "ether1",
                }
            ],
            [
                {
                    "device": {"name": "device1-live", "mac": "aa-bb-cc-dd-ee-01"},
                    "network_device": "poe-switch-01",
                    "interface": "ether1",
                }
            ],
        )

        self.assertTrue(report.ok)
        self.assertEqual(
            report.to_dict()["matches"][0]["keys"],
            ["mac:aa:bb:cc:dd:ee:01"],
        )


def _attachment(
    name: str,
    mac: str,
    network_device: str,
    interface: str,
) -> AttachmentRecord:
    return AttachmentRecord(
        device=DeviceRecord(name=name, mac=mac),
        network_device=network_device,
        interface=interface,
    )


if __name__ == "__main__":
    unittest.main()
