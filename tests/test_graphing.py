import tempfile
import unittest
from pathlib import Path

from network_lang import (
    OperationResult,
    bar_graph,
    counter_rate_field_name,
    counter_rate_records,
    line_graph,
    to_html,
)


class GraphingTests(unittest.TestCase):
    def test_line_graph_groups_points_and_sorts_timestamps(self):
        records = [
            {
                "timestamp": "2026-05-27T00:00:10Z",
                "rx_errors": 3,
                "interface": "ether2",
            },
            {
                "timestamp": "2026-05-27T00:00:00Z",
                "rx_errors": 1,
                "interface": "ether1",
            },
            {
                "timestamp": "2026-05-27T00:00:05Z",
                "rx_errors": 2,
                "interface": "ether1",
            },
            {
                "timestamp": "2026-05-27T00:00:00Z",
                "rx_errors": "bad-value",
                "interface": "ether2",
            },
        ]

        graph = line_graph(
            records,
            x="timestamp",
            y="rx_errors",
            group_by="interface",
            title="RX Errors by Interface",
        )

        self.assertEqual(graph.kind, "line")
        self.assertEqual(graph.title, "RX Errors by Interface")
        self.assertEqual(
            graph.x_labels,
            (
                "2026-05-27T00:00:00Z",
                "2026-05-27T00:00:05Z",
                "2026-05-27T00:00:10Z",
            ),
        )
        self.assertEqual([series.name for series in graph.series], ["ether1", "ether2"])
        self.assertEqual(
            [(point.x, point.y) for point in graph.series[0].points],
            [("2026-05-27T00:00:00Z", 1.0), ("2026-05-27T00:00:05Z", 2.0)],
        )
        self.assertEqual(
            [(point.x, point.y) for point in graph.series[1].points],
            [("2026-05-27T00:00:10Z", 3.0)],
        )
        self.assertEqual(graph.source_count, 4)
        self.assertEqual(graph.plotted_count, 3)
        self.assertEqual(graph.dropped_count, 1)

    def test_line_graph_supports_dotted_record_paths(self):
        records = [
            {
                "sample": {"timestamp": 1},
                "metrics": {"rx_errors": 10},
                "iface": {"name": "ether1"},
            },
            {
                "sample": {"timestamp": 2},
                "metrics": {"rx_errors": 11},
                "iface": {"name": "ether1"},
            },
            {
                "sample": {"timestamp": 1},
                "metrics": {"rx_errors": 4},
                "iface": {"name": "ether2"},
            },
        ]

        graph = line_graph(
            records,
            x="sample.timestamp",
            y="metrics.rx_errors",
            group_by="iface.name",
        )

        self.assertEqual(graph.x_labels, ("1", "2"))
        self.assertEqual([series.name for series in graph.series], ["ether1", "ether2"])
        self.assertEqual(
            [(point.x, point.y) for point in graph.series[0].points],
            [("1", 10.0), ("2", 11.0)],
        )
        self.assertEqual(
            [(point.x, point.y) for point in graph.series[1].points],
            [("1", 4.0)],
        )

    def test_to_html_writes_svg_document(self):
        graph = line_graph(
            [
                {"timestamp": "2026-05-27T00:00:00Z", "rx_errors": 1, "interface": "ether1"},
                {"timestamp": "2026-05-27T00:01:00Z", "rx_errors": 3, "interface": "ether1"},
            ],
            x="timestamp",
            y="rx_errors",
            group_by="interface",
            title="RX Errors",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "graphs" / "rx_errors.html"
            written = to_html(graph, output)

            self.assertEqual(written, output)
            self.assertTrue(output.exists())
            html = output.read_text(encoding="utf-8")

        self.assertIn("<svg", html)
        self.assertIn("RX Errors", html)
        self.assertIn("ether1", html)

    def test_to_html_places_flat_zero_line_on_baseline(self):
        graph = line_graph(
            [
                {"timestamp": "2026-05-27T00:00:00Z", "rx_errors": 0, "interface": "ether1"},
                {"timestamp": "2026-05-27T00:01:00Z", "rx_errors": 0, "interface": "ether1"},
            ],
            x="timestamp",
            y="rx_errors",
            group_by="interface",
            title="RX Errors",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "rx_errors.html"
            to_html(graph, output)
            html = output.read_text(encoding="utf-8")

        self.assertIn("All plotted values are 0, so series overlap.", html)
        self.assertIn('cy="416.00"', html)
        self.assertNotIn('cy="228.00"', html)

    def test_to_html_formats_timestamp_axis_labels(self):
        graph = line_graph(
            [
                {
                    "timestamp": "2026-05-27T11:40:10.897319Z",
                    "rx_mbps": 0.03,
                    "interface": "bridge1",
                },
                {
                    "timestamp": "2026-05-27T11:40:16.441219Z",
                    "rx_mbps": 0.04,
                    "interface": "bridge1",
                },
            ],
            x="timestamp",
            y="rx_mbps",
            group_by="interface",
            title="RX Mbps",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "rx_mbps.html"
            to_html(graph, output)
            html = output.read_text(encoding="utf-8")

        self.assertIn(">11:40:10</text>", html)
        self.assertIn(">11:40:16</text>", html)
        self.assertIn("bridge1 | 11:40:10 | 0.03", html)
        self.assertNotIn("2026-05-27T11:40:16.4...</text>", html)
        self.assertNotIn("bridge1 | 2026-05-27T11:40:16.441219Z", html)

    def test_line_graph_accepts_operation_result_snapshot(self):
        result = OperationResult(
            ok=True,
            operation="network.interfaces.list",
            target="edge-01",
            capability="supported",
            adapter={"vendor": "mikrotik"},
            data=[
                {"name": "ether1", "rx_error": 2},
                {"default_name": "ether2", "rx_errors": 4},
                {"name": "ether3"},
            ],
        )

        graph = line_graph(
            result,
            y="rx_errors",
            group_by="interface",
            title="RX Errors by Interface",
            sample_at="2026-05-27T00:00:00Z",
        )

        self.assertEqual(graph.x_labels, ("2026-05-27T00:00:00Z",))
        self.assertEqual([series.name for series in graph.series], ["ether1", "ether2"])
        self.assertEqual(
            [(point.x, point.y) for point in graph.series[0].points],
            [("2026-05-27T00:00:00Z", 2.0)],
        )
        self.assertEqual(
            [(point.x, point.y) for point in graph.series[1].points],
            [("2026-05-27T00:00:00Z", 4.0)],
        )
        self.assertEqual(graph.source_count, 3)
        self.assertEqual(graph.plotted_count, 2)
        self.assertEqual(graph.dropped_count, 1)

    def test_line_graph_supports_aliases_fields_filters_and_multiple_metrics(self):
        records = [
            {"ts": 1, "iface": "ether1", "rx": 10, "tx": 20, "running": True},
            {"ts": 2, "iface": "ether1", "rx": 11, "tx": 22, "running": True},
            {"ts": 2, "iface": "ether2", "rx": 2, "tx": 4, "running": False},
        ]

        graph = line_graph(
            records,
            x="timestamp",
            y=("rx_mbps", "tx_mbps"),
            group_by="interface",
            aliases={
                "timestamp": ("ts",),
                "interface": ("iface",),
            },
            fields={
                "rx_mbps": lambda row: row["rx"] * 8,
                "tx_mbps": lambda row: row["tx"] * 8,
            },
            where=lambda row: bool(row["running"]),
        )

        self.assertEqual(graph.x_labels, ("1", "2"))
        self.assertEqual(
            [series.name for series in graph.series],
            [
                "ether1 / rx_mbps",
                "ether1 / tx_mbps",
            ],
        )
        self.assertEqual(
            [(point.x, point.y) for point in graph.series[0].points],
            [("1", 80.0), ("2", 88.0)],
        )
        self.assertEqual(
            [(point.x, point.y) for point in graph.series[1].points],
            [("1", 160.0), ("2", 176.0)],
        )
        self.assertEqual(graph.dropped_count, 1)

    def test_counter_rate_records_adds_mbps_fields(self):
        records = [
            {
                "timestamp": "2026-05-27T00:00:00Z",
                "interface": "ether1",
                "rx_byte": 1000,
                "tx_byte": 2000,
            },
            {
                "timestamp": "2026-05-27T00:00:10Z",
                "interface": "ether1",
                "rx_byte": 11000,
                "tx_byte": 22000,
            },
        ]

        rated = counter_rate_records(
            records,
            counters=("rx_byte", "tx_byte"),
            group_by="interface",
            scale=0.000008,
            suffix="_mbps",
        )

        self.assertEqual(len(rated), 1)
        self.assertEqual(rated[0]["interface"], "ether1")
        self.assertAlmostEqual(rated[0]["rx_mbps"], 0.008)
        self.assertAlmostEqual(rated[0]["tx_mbps"], 0.016)
        self.assertEqual(
            counter_rate_field_name("rx_byte", suffix="_mbps"),
            "rx_mbps",
        )

    def test_counter_rate_records_groups_and_skips_counter_resets(self):
        records = [
            {"timestamp": 0, "interface": "ether1", "rx_byte": 1000},
            {"timestamp": 10, "interface": "ether1", "rx_byte": 2000},
            {"timestamp": 20, "interface": "ether1", "rx_byte": 100},
            {"timestamp": 30, "interface": "ether1", "rx_byte": 1100},
            {"timestamp": 0, "interface": "ether2", "rx_byte": 5000},
            {"timestamp": 10, "interface": "ether2", "rx_byte": 6000},
        ]

        rated = counter_rate_records(
            records,
            counters="rx_byte",
            group_by="interface",
            scale=1,
        )

        self.assertEqual(
            [(row["interface"], row["timestamp"], row["rx_byte_rate"]) for row in rated],
            [
                ("ether1", 10, 100.0),
                ("ether1", 30, 100.0),
                ("ether2", 10, 100.0),
            ],
        )

    def test_bar_graph_counts_categorical_operation_result_fields(self):
        result = OperationResult(
            ok=True,
            operation="network.routes.list",
            target="edge-01",
            capability="supported",
            adapter={"vendor": "mikrotik"},
            data=[
                {"dst_address": "0.0.0.0/0", "routing_table": "main"},
                {"dst_address": "10.0.0.0/24", "routing_table": "main"},
                {"dst_address": "10.0.1.0/24", "routing_table": "customer"},
                {"gateway": "192.0.2.1"},
            ],
        )

        graph = bar_graph(
            result,
            x="routing_table",
            title="Routes by Table",
        )

        self.assertEqual(graph.kind, "bar")
        self.assertEqual(graph.x_labels, ("main", "customer"))
        self.assertEqual(
            [(point.x, point.y) for point in graph.series[0].points],
            [("main", 2.0), ("customer", 1.0)],
        )
        self.assertEqual(graph.source_count, 4)
        self.assertEqual(graph.plotted_count, 3)
        self.assertEqual(graph.dropped_count, 1)

    def test_bar_graph_aggregates_numeric_values_by_category(self):
        graph = bar_graph(
            [
                {"interface": "ether1", "rx_errors": 2},
                {"interface": "ether1", "rx_errors": 3},
                {"interface": "ether2", "rx_errors": 7},
            ],
            x="interface",
            y="rx_errors",
        )

        self.assertEqual(graph.y, "rx_errors")
        self.assertEqual(
            [(point.x, point.y) for point in graph.series[0].points],
            [("ether1", 5.0), ("ether2", 7.0)],
        )

        latest = bar_graph(
            [
                {"interface": "ether1", "rx_errors": 2},
                {"interface": "ether1", "rx_errors": 3},
            ],
            x="interface",
            y="rx_errors",
            aggregate="latest",
        )

        self.assertEqual(
            [(point.x, point.y) for point in latest.series[0].points],
            [("ether1", 3.0)],
        )

    def test_to_html_writes_bar_graph_document(self):
        graph = bar_graph(
            [
                {"routing_table": "main"},
                {"routing_table": "main"},
                {"routing_table": "customer"},
            ],
            x="routing_table",
            title="Routes by Table",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "routes.html"
            to_html(graph, output)
            html = output.read_text(encoding="utf-8")

        self.assertIn("<svg", html)
        self.assertIn("Routes by Table", html)
        self.assertIn("main", html)


if __name__ == "__main__":
    unittest.main()
