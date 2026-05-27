from __future__ import annotations

import os

from network_lang import target_device
from network_lang.exporters import to_html

target = os.environ.get("NETWORK_LANG_TARGET", "edge-01")
device = target_device(target)

graph = device.graph(
    "network.interfaces.list",
    y=("rx_mbps", "tx_mbps"),
    samples=12,
    interval=5,
)

to_html(graph, "interface_mbps.html")