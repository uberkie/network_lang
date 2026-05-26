import unittest

from network_lang import (
    AttachmentRecord,
    DeviceRecord,
    FlowObservation,
    flow_observations_to_attachments,
    flow_observations_to_devices,
    preflight_interface_operation,
    build_operation,
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
