from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

from .reconcile import DeviceRecord
from .topology import AttachmentRecord

FlowEndpoint = Literal["src", "dst", "both"]


@dataclass(frozen=True)
class FlowObservation:
    exporter: str
    src_host: str
    dst_host: str
    ingress_interface: str | None = None
    egress_interface: str | None = None
    protocol: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    bytes: int = 0
    packets: int = 0
    window_start: str | None = None
    window_end: str | None = None
    source: str = "netflow"
    src_mac: str | None = None
    dst_mac: str | None = None
    src_identifiers: tuple[str, ...] = ()
    dst_identifiers: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "exporter": self.exporter,
            "src_host": self.src_host,
            "dst_host": self.dst_host,
            "ingress_interface": self.ingress_interface,
            "egress_interface": self.egress_interface,
            "protocol": self.protocol,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "bytes": self.bytes,
            "packets": self.packets,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "source": self.source,
            "src_mac": self.src_mac,
            "dst_mac": self.dst_mac,
            "src_identifiers": list(self.src_identifiers),
            "dst_identifiers": list(self.dst_identifiers),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class FlowTargetResolution:
    target: str
    host: str
    network_device: str
    interface: str | None
    direction: str
    confidence: str
    observation: FlowObservation

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "host": self.host,
            "network_device": self.network_device,
            "interface": self.interface,
            "direction": self.direction,
            "confidence": self.confidence,
            "observation": self.observation.to_dict(),
        }


def flow_observations_to_devices(
    flows: Iterable[FlowObservation | dict[str, Any]],
    endpoint: FlowEndpoint = "src",
) -> tuple[DeviceRecord, ...]:
    """

    Args:
        flows:
        endpoint:

    Returns:

    """
    devices: list[DeviceRecord] = []
    for flow in (_flow(record) for record in flows):
        if endpoint in {"src", "both"}:
            devices.append(_flow_device(flow, "src"))
        if endpoint in {"dst", "both"}:
            devices.append(_flow_device(flow, "dst"))
    return tuple(devices)


def flow_observations_to_attachments(
    flows: Iterable[FlowObservation | dict[str, Any]],
    endpoint: FlowEndpoint = "src",
) -> tuple[AttachmentRecord, ...]:
    """

    Args:
        flows:
        endpoint:

    Returns:

    """
    attachments: list[AttachmentRecord] = []
    for flow in (_flow(record) for record in flows):
        if endpoint in {"src", "both"} and flow.ingress_interface:
            attachments.append(
                AttachmentRecord(
                    device=_flow_device(flow, "src"),
                    network_device=flow.exporter,
                    interface=flow.ingress_interface,
                    source=flow.source,
                    metadata=_flow_metadata(flow, "src"),
                )
            )
        if endpoint in {"dst", "both"} and flow.egress_interface:
            attachments.append(
                AttachmentRecord(
                    device=_flow_device(flow, "dst"),
                    network_device=flow.exporter,
                    interface=flow.egress_interface,
                    source=flow.source,
                    metadata=_flow_metadata(flow, "dst"),
                )
            )
    return tuple(attachments)


def resolve_flow_target(
    target: str,
    flows: Iterable[FlowObservation | dict[str, Any]],
) -> FlowTargetResolution | None:
    """

    Args:
        target:
        flows:

    Returns:

    """
    host = _target_host(target)
    candidates: list[FlowTargetResolution] = []

    for flow in (_flow(record) for record in flows):
        if _same_host(host, flow.src_host):
            candidates.append(
                FlowTargetResolution(
                    target=target,
                    host=flow.src_host,
                    network_device=flow.exporter,
                    interface=flow.ingress_interface,
                    direction="src",
                    confidence="medium_high" if flow.ingress_interface else "medium",
                    observation=flow,
                )
            )
        if _same_host(host, flow.dst_host):
            candidates.append(
                FlowTargetResolution(
                    target=target,
                    host=flow.dst_host,
                    network_device=flow.exporter,
                    interface=flow.egress_interface,
                    direction="dst",
                    confidence="medium_high" if flow.egress_interface else "medium",
                    observation=flow,
                )
            )

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda resolution: (
            resolution.interface is not None,
            resolution.observation.bytes,
            resolution.observation.packets,
        ),
    )


def _flow(record: FlowObservation | dict[str, Any]) -> FlowObservation:
    if isinstance(record, FlowObservation):
        return record
    return FlowObservation(**record)


def _flow_device(flow: FlowObservation, direction: Literal["src", "dst"]) -> DeviceRecord:
    """

    Args:
        flow:
        direction:

    Returns:

    """
    if direction == "src":
        host = flow.src_host
        mac = flow.src_mac
        identifiers = flow.src_identifiers
    else:
        host = flow.dst_host
        mac = flow.dst_mac
        identifiers = flow.dst_identifiers

    return DeviceRecord(
        host=host,
        mac=mac,
        source=flow.source,
        identifiers=identifiers,
        metadata=_flow_metadata(flow, direction),
    )


def _flow_metadata(flow: FlowObservation, direction: str) -> dict[str, Any]:
    """

    Args:
        flow:
        direction:

    Returns:

    """
    peer_host = flow.dst_host if direction == "src" else flow.src_host
    interface = (
        flow.ingress_interface if direction == "src" else flow.egress_interface
    )
    metadata = {
        "exporter": flow.exporter,
        "direction": direction,
        "peer_host": peer_host,
        "interface": interface,
        "ingress_interface": flow.ingress_interface,
        "egress_interface": flow.egress_interface,
        "protocol": flow.protocol,
        "src_port": flow.src_port,
        "dst_port": flow.dst_port,
        "bytes": flow.bytes,
        "packets": flow.packets,
        "window_start": flow.window_start,
        "window_end": flow.window_end,
    }
    metadata.update(flow.metadata)
    return {key: value for key, value in metadata.items() if value is not None}


def _target_host(target: str) -> str:
    value = target.strip()
    if value.lower().startswith("ip:"):
        value = value[3:]
    return _normalize_host(value)


def _same_host(left: str, right: str) -> bool:
    return _normalize_host(left) == _normalize_host(right)


def _normalize_host(host: str) -> str:
    value = host.strip().lower()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return value
