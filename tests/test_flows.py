import json
import tempfile
import unittest

from network_lang import (
    FLOW_RECON_POLICY,
    AttachmentRecord,
    DeviceRecord,
    FlowExpectation,
    FlowObservation,
    apply_flow_recon_policy,
    classify_flow_device,
    flow_observations_to_attachments,
    flow_observations_to_devices,
    flow_records_to_devices,
    load_flow_devices,
    preflight_interface_operation,
    build_operation,
    reconcile_flow_envelope,
    reconcile_devices,
    resolve_flow_target,
)


class FlowObservationTests(unittest.TestCase):
    def test_flow_observation_becomes_source_attachment(self):
        flow = FlowObservation(
            exporter="tower-nas-03",
            src_host="10.20.30.45",
            dst_host="8.8.8.8",
            ingress_interface="pppoe-customer0172",
            egress_interface="uplink-core",
            protocol="udp",
            dst_port=53,
            bytes=12000,
            packets=40,
            src_identifiers=("radius:user/customer0172",),
        )

        attachments = flow_observations_to_attachments([flow])

        self.assertEqual(len(attachments), 1)
        attachment = attachments[0]
        self.assertEqual(attachment.device.host, "10.20.30.45")
        self.assertEqual(attachment.network_device, "tower-nas-03")
        self.assertEqual(attachment.interface, "pppoe-customer0172")
        self.assertEqual(attachment.source, "netflow")
        self.assertEqual(attachment.metadata["peer_host"], "8.8.8.8")
        self.assertEqual(attachment.metadata["bytes"], 12000)
        self.assertIn("radius:user/customer0172", attachment.device.identifiers)

    def test_flow_observation_can_include_both_endpoints(self):
        flow = FlowObservation(
            exporter="core-01",
            src_host="10.20.30.45",
            dst_host="203.0.113.10",
            ingress_interface="customers",
            egress_interface="transit",
        )

        devices = flow_observations_to_devices([flow], endpoint="both")
        attachments = flow_observations_to_attachments([flow], endpoint="both")

        self.assertEqual(
            [device.host for device in devices],
            ["10.20.30.45", "203.0.113.10"],
        )
        self.assertEqual(
            [
                (attachment.device.host, attachment.interface)
                for attachment in attachments
            ],
            [("10.20.30.45", "customers"), ("203.0.113.10", "transit")],
        )

    def test_classifies_flow_device_records(self):
        self.assertEqual(
            classify_flow_device(
                {
                    "host": "192.168.4.1",
                    "source": "netflow:v5",
                    "metadata": {"exporter": "192.168.4.1"},
                }
            ),
            "exporter",
        )
        self.assertEqual(
            classify_flow_device(
                {
                    "host": "8.8.8.8",
                    "source": "netflow:v5",
                    "metadata": {"exporter": "192.168.4.1", "direction": "dst"},
                }
            ),
            "public_external",
        )
        self.assertEqual(
            classify_flow_device(
                {
                    "host": "192.168.11.20",
                    "source": "netflow:v5",
                    "metadata": {"exporter": "192.168.4.1"},
                },
                customer_hosts=("192.168.11.20",),
            ),
            "customer_endpoint",
        )
        self.assertEqual(
            classify_flow_device(
                {
                    "host": "255.255.255.255",
                    "source": "netflow:v5",
                    "metadata": {"exporter": "192.168.4.1", "direction": "dst"},
                }
            ),
            "ignored_peer",
        )

    def test_flow_records_to_devices_filters_internal_records(self):
        records = [
            {
                "host": "8.8.8.8",
                "source": "netflow:v5",
                "identifiers": [],
                "metadata": {"exporter": "192.168.4.1", "direction": "src"},
            },
            {
                "host": "192.168.4.1",
                "source": "netflow:v5",
                "identifiers": [],
                "metadata": {"exporter": "192.168.4.1", "direction": "src"},
            },
            {
                "host": "192.168.4.240",
                "source": "netflow:v5",
                "identifiers": [],
                "metadata": {"exporter": "192.168.4.1", "direction": "dst"},
            },
            {
                "host": "192.168.4.240",
                "source": "netflow:v5",
                "identifiers": [],
                "metadata": {"exporter": "192.168.4.1", "direction": "src"},
            },
            {
                "host": "255.255.255.255",
                "source": "netflow:v5",
                "identifiers": [],
                "metadata": {"exporter": "192.168.4.1", "direction": "dst"},
            },
        ]

        devices = flow_records_to_devices(records, scope="internal")

        self.assertEqual([device.host for device in devices], ["192.168.4.240"])
        self.assertEqual(devices[0].metadata["flow_class"], "unknown_internal")

        external = flow_records_to_devices(records, scope="external")

        self.assertEqual([device.host for device in external], ["8.8.8.8"])
        self.assertEqual(external[0].metadata["flow_class"], "public_external")

        ignored = flow_records_to_devices(records, scope="ignored")

        self.assertEqual([device.host for device in ignored], ["255.255.255.255"])
        self.assertEqual(ignored[0].metadata["flow_class"], "ignored_peer")

        internal_with_peers = flow_records_to_devices(
            records,
            scope="internal",
            include_external_peers=True,
        )

        self.assertEqual(
            [device.host for device in internal_with_peers],
            ["8.8.8.8", "192.168.4.240"],
        )

        all_devices = flow_records_to_devices(
            records,
            scope="all",
            exclude_exporters=False,
        )

        self.assertEqual(
            [device.host for device in all_devices],
            ["8.8.8.8", "192.168.4.1", "192.168.4.240", "255.255.255.255"],
        )

    def test_load_flow_devices_reads_jsonl_and_filters_scope(self):
        records = [
            {
                "host": "40.79.163.155",
                "source": "netflow:v5",
                "identifiers": [],
                "metadata": {"exporter": "192.168.4.1", "direction": "src"},
            },
            {
                "host": "192.168.4.240",
                "source": "netflow:v5",
                "identifiers": [],
                "metadata": {"exporter": "192.168.4.1", "direction": "dst"},
            },
        ]
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")
            handle.flush()

            devices = load_flow_devices(handle.name, scope="internal")

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].host, "192.168.4.240")

    def test_apply_flow_recon_policy_builds_operator_summary(self):
        expected = [DeviceRecord(name="customer0172", host="192.168.4.240")]
        records = [
            {
                "host": "192.168.4.240",
                "source": "netflow:v5",
                "metadata": {
                    "exporter": "192.168.4.1",
                    "direction": "dst",
                    "peer_host": "150.171.109.3",
                    "src_port": 443,
                    "input_interface_index": 1,
                    "output_interface_index": 8,
                    "interface_index": 8,
                },
            },
            {
                "host": "192.168.11.20",
                "source": "netflow:v5",
                "metadata": {
                    "exporter": "192.168.4.1",
                    "direction": "src",
                    "peer_host": "8.8.8.8",
                    "dst_port": 53,
                    "input_interface_index": 0,
                    "output_interface_index": 1,
                    "interface_index": 0,
                },
            },
            {
                "host": "192.168.4.100",
                "source": "netflow:v5",
                "metadata": {
                    "exporter": "192.168.4.1",
                    "direction": "src",
                    "peer_host": "1.1.1.1",
                    "dst_port": 53,
                    "input_interface_index": 8,
                    "output_interface_index": 1,
                    "interface_index": 8,
                },
            },
            {
                "host": "8.8.8.8",
                "source": "netflow:v5",
                "metadata": {
                    "exporter": "192.168.4.1",
                    "direction": "dst",
                    "peer_host": "192.168.11.20",
                    "src_port": 53,
                    "interface_index": 1,
                },
            },
        ]
        observed = flow_records_to_devices(
            records,
            scope="all",
            customer_hosts=("192.168.4.240",),
        )

        report = apply_flow_recon_policy(reconcile_devices(expected, observed))

        self.assertEqual(
            FLOW_RECON_POLICY["unknown_internal"],
            "report",
        )
        self.assertFalse(report.ok)
        self.assertEqual(report.exit_code, 1)
        self.assertEqual(report.to_dict()["exit_code"], 1)
        self.assertEqual(
            [finding.host for finding in report.matched_customer_endpoints],
            ["192.168.4.240"],
        )
        self.assertEqual(
            [finding.host for finding in report.unknown_internal_hosts],
            ["192.168.11.20", "192.168.4.100"],
        )
        self.assertEqual(
            report.unknown_internal_hosts[0].summary,
            "192.168.11.20 seen via exporter 192.168.4.1, "
            "output interface 1, DNS to 8.8.8.8",
        )
        self.assertEqual(
            report.unknown_internal_hosts[1].summary,
            "192.168.4.100 seen via exporter 192.168.4.1, "
            "interface 8, DNS to 1.1.1.1",
        )
        self.assertEqual(
            [finding.host for finding in report.external_peers],
            ["8.8.8.8"],
        )
        self.assertEqual(
            report.to_text(),
            "\n".join(
                [
                    "Unknown internal hosts observed: 2",
                    "Matched customer endpoints: 1",
                    "Infrastructure observed: 0",
                    "External peers ignored: 1",
                    "",
                    "Unknown internal hosts observed:",
                    "- 192.168.11.20 seen via exporter 192.168.4.1, "
                    "output interface 1, DNS to 8.8.8.8",
                    "- 192.168.4.100 seen via exporter 192.168.4.1, "
                    "interface 8, DNS to 1.1.1.1",
                    "",
                    "Matched customer endpoints:",
                    "- 192.168.4.240 score=95 source=netflow:v5 "
                    "exporter=192.168.4.1 interface=8",
                ]
            ),
        )

    def test_flow_recon_policy_exit_code_is_zero_without_unknown_internal(self):
        expected = [DeviceRecord(name="customer0172", host="192.168.4.240")]
        observed = flow_records_to_devices(
            [
                {
                    "host": "192.168.4.240",
                    "source": "netflow:v5",
                    "metadata": {
                        "exporter": "192.168.4.1",
                        "direction": "src",
                    },
                },
                {
                    "host": "192.168.4.100",
                    "source": "netflow:v5",
                    "metadata": {
                        "exporter": "192.168.4.1",
                        "direction": "src",
                        "interface_index": 8,
                    },
                }
            ],
            customer_hosts=("192.168.4.240",),
            known_infrastructure=("192.168.4.100",),
        )

        report = apply_flow_recon_policy(reconcile_devices(expected, observed))

        self.assertTrue(report.ok)
        self.assertEqual(report.exit_code, 0)
        self.assertIn("Infrastructure observed: 1", report.to_text())
        self.assertIn(
            "- 192.168.4.100 source=netflow:v5 exporter=192.168.4.1 interface=8",
            report.to_text(),
        )

    def test_resolve_ip_target_from_flow_sample(self):
        flows = [
            FlowObservation(
                exporter="tower-nas-01",
                src_host="10.20.30.45",
                dst_host="8.8.8.8",
                ingress_interface="pppoe-customer0172",
                bytes=100,
            ),
            FlowObservation(
                exporter="tower-nas-03",
                src_host="10.20.30.45",
                dst_host="1.1.1.1",
                ingress_interface="pppoe-customer0172",
                bytes=5000,
            ),
        ]

        resolution = resolve_flow_target("ip:10.20.30.45", flows)

        self.assertIsNotNone(resolution)
        self.assertEqual(resolution.network_device, "tower-nas-03")
        self.assertEqual(resolution.interface, "pppoe-customer0172")
        self.assertEqual(resolution.direction, "src")
        self.assertEqual(resolution.confidence, "medium_high")

    def test_resolve_flow_target_returns_none_for_unknown_host(self):
        flow = FlowObservation(
            exporter="tower-nas-03",
            src_host="10.20.30.45",
            dst_host="8.8.8.8",
        )

        self.assertIsNone(resolve_flow_target("ip:10.20.30.99", [flow]))

    def test_resolve_flow_target_matches_identifier(self):
        flow = FlowObservation(
            exporter="tower-east",
            src_host="10.20.30.45",
            dst_host="8.8.8.8",
            ingress_interface="pppoe-customer0172",
            src_identifiers=("radius:user/customer0172",),
        )

        resolution = resolve_flow_target("customer0172", [flow])

        self.assertIsNotNone(resolution)
        self.assertEqual(resolution.host, "10.20.30.45")
        self.assertEqual(resolution.network_device, "tower-east")
        self.assertEqual(resolution.interface, "pppoe-customer0172")

    def test_reconcile_flow_envelope_flags_degraded_wireless_link(self):
        expected = FlowExpectation(
            target="customer0172",
            network_device="tower-east",
            interface="pppoe-customer0172",
            envelope={
                "rssi": {"min": -65, "max": -45, "severity": "high"},
                "ccq": {"min": 80, "severity": "high"},
                "mtu": 1500,
                "rx_errors_delta": {"max": 0, "severity": "high"},
                "traffic_mbps": {"min": 1, "max": 20, "severity": "medium"},
            },
        )
        flow = FlowObservation(
            exporter="tower-east",
            src_host="10.20.30.45",
            dst_host="8.8.8.8",
            ingress_interface="pppoe-customer0172",
            src_identifiers=("radius:user/customer0172",),
            metadata={
                "rssi": -78,
                "ccq": 42,
                "mtu": 1500,
                "rx_errors_delta": 12,
                "traffic_mbps": 0.4,
            },
        )

        report = reconcile_flow_envelope(expected, [flow])

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, "investigate_first")
        self.assertEqual(report.identity_confidence, 90)
        self.assertEqual(report.topology_confidence, 100)
        self.assertEqual(report.health_score, 20)
        self.assertEqual(report.action_safety, 20)
        self.assertEqual(
            report.suggested_cause,
            "wireless_or_physical_layer_issue",
        )
        self.assertIn("wireless link quality is degraded", report.summary)

    def test_reconcile_flow_envelope_allows_healthy_link(self):
        expected = {
            "target": "customer0172",
            "network_device": "tower-east",
            "interface": "pppoe-customer0172",
            "envelope": {
                "rssi": (-65, -45),
                "ccq": {"min": 80},
                "mtu": 1500,
                "rx_errors_delta": {"max": 0},
                "traffic_mbps": (1, 20),
            },
        }
        flow = FlowObservation(
            exporter="tower-east",
            src_host="10.20.30.45",
            dst_host="8.8.8.8",
            ingress_interface="pppoe-customer0172",
            src_identifiers=("radius:user/customer0172",),
            metadata={
                "rssi": -55,
                "ccq": 92,
                "mtu": 1500,
                "rx_errors_delta": 0,
                "traffic_mbps": 8,
            },
        )

        report = reconcile_flow_envelope(expected, [flow])

        self.assertTrue(report.ok)
        self.assertEqual(report.decision, "safe")
        self.assertEqual(report.health_score, 100)

    def test_flow_attachments_feed_topology_preflight(self):
        operation = build_operation(
            "network.interfaces.disable",
            target="tower-nas-03",
            name="pppoe-customer0172",
        )
        expected = [
            AttachmentRecord(
                device=DeviceRecord(
                    name="customer0172",
                    identifiers=("radius:user/customer0172",),
                ),
                network_device="tower-nas-03",
                interface="pppoe-customer0172",
            )
        ]
        flow = FlowObservation(
            exporter="tower-nas-07",
            src_host="10.20.30.45",
            dst_host="8.8.8.8",
            ingress_interface="pppoe-customer0172",
            src_identifiers=("radius:user/customer0172",),
        )

        report = preflight_interface_operation(
            operation,
            expected,
            flow_observations_to_attachments([flow]),
        )

        self.assertFalse(report.ok)
        self.assertIn("customer0172 expected on tower-nas-03", report.risks[0])
        self.assertIn("but observed on tower-nas-07", report.risks[0])


if __name__ == "__main__":
    unittest.main()
