from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

from .reconcile import DeviceRecord, ReconciliationReport
from .topology import AttachmentRecord

FlowEndpoint = Literal["src", "dst", "both"]
FlowReconAction = Literal["match_or_score", "report", "ignore", "infrastructure"]
FlowDeviceClass = Literal[
    "public_external",
    "private_internal",
    "exporter",
    "known_infrastructure",
    "customer_endpoint",
    "unknown_internal",
    "ignored_peer",
]
FlowDeviceScope = Literal[
    "all",
    "internal",
    "external",
    "ignored",
    "managed",
    "customer",
    "infrastructure",
    "unknown_internal",
]
FLOW_RECON_POLICY: Mapping[FlowDeviceClass, FlowReconAction] = {
    "customer_endpoint": "match_or_score",
    "unknown_internal": "report",
    "private_internal": "report",
    "public_external": "ignore",
    "ignored_peer": "ignore",
    "exporter": "infrastructure",
    "known_infrastructure": "infrastructure",
}


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


@dataclass(frozen=True)
class FlowExpectation:
    target: str
    network_device: str | None = None
    interface: str | None = None
    envelope: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "network_device": self.network_device,
            "interface": self.interface,
            "envelope": self.envelope,
        }


@dataclass(frozen=True)
class FlowSignalCheck:
    signal: str
    status: str
    expected: Any
    observed: Any
    severity: str
    score: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal,
            "status": self.status,
            "expected": self.expected,
            "observed": self.observed,
            "severity": self.severity,
            "score": self.score,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class FlowEnvelopeReport:
    decision: str
    identity_confidence: int
    topology_confidence: int
    health_score: int
    action_safety: int
    summary: str
    suggested_cause: str | None
    action_safety_reason: str
    evidence: tuple[FlowSignalCheck, ...]
    resolution: FlowTargetResolution | None = None

    @property
    def ok(self) -> bool:
        return self.decision == "safe"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "decision": self.decision,
            "identity_confidence": self.identity_confidence,
            "topology_confidence": self.topology_confidence,
            "health_score": self.health_score,
            "action_safety": self.action_safety,
            "summary": self.summary,
            "suggested_cause": self.suggested_cause,
            "action_safety_reason": self.action_safety_reason,
            "evidence": [check.to_dict() for check in self.evidence],
            "resolution": self.resolution.to_dict() if self.resolution else None,
        }


@dataclass(frozen=True)
class FlowReconFinding:
    host: str
    flow_class: str
    action: str
    summary: str
    device: DeviceRecord
    expected: DeviceRecord | None = None
    score: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "flow_class": self.flow_class,
            "action": self.action,
            "summary": self.summary,
            "device": self.device.to_dict(),
            "expected": self.expected.to_dict() if self.expected else None,
            "score": self.score,
        }


@dataclass(frozen=True)
class FlowReconPolicyReport:
    matched_customer_endpoints: tuple[FlowReconFinding, ...]
    unknown_internal_hosts: tuple[FlowReconFinding, ...]
    infrastructure: tuple[FlowReconFinding, ...]
    external_peers: tuple[FlowReconFinding, ...]
    ignored_peers: tuple[FlowReconFinding, ...]
    missing_expected: tuple[DeviceRecord, ...]

    @property
    def ok(self) -> bool:
        return not self.unknown_internal_hosts and not self.missing_expected

    @property
    def exit_code(self) -> int:
        return 1 if self.unknown_internal_hosts else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "exit_code": self.exit_code,
            "matched_customer_endpoints": [
                finding.to_dict() for finding in self.matched_customer_endpoints
            ],
            "unknown_internal_hosts": [
                finding.to_dict() for finding in self.unknown_internal_hosts
            ],
            "infrastructure": [finding.to_dict() for finding in self.infrastructure],
            "external_peers": [finding.to_dict() for finding in self.external_peers],
            "ignored_peers": [finding.to_dict() for finding in self.ignored_peers],
            "missing_expected": [
                device.to_dict() for device in self.missing_expected
            ],
        }

    def to_text(self) -> str:
        sections = [
            "\n".join(
                [
                    f"Unknown internal hosts observed: {len(self.unknown_internal_hosts)}",
                    f"Matched customer endpoints: {len(self.matched_customer_endpoints)}",
                    f"Infrastructure observed: {len(self.infrastructure)}",
                    f"External peers ignored: {len(self.external_peers)}",
                ]
            )
        ]
        if self.unknown_internal_hosts:
            sections.append(
                _finding_section(
                    "Unknown internal hosts observed",
                    self.unknown_internal_hosts,
                    use_summary=True,
                )
            )
        if self.matched_customer_endpoints:
            sections.append(
                _finding_section(
                    "Matched customer endpoints",
                    self.matched_customer_endpoints,
                    detail="matched",
                )
            )
        if self.infrastructure:
            sections.append(
                _finding_section(
                    "Infrastructure observed",
                    self.infrastructure,
                    detail="infrastructure",
                )
            )
        if self.missing_expected:
            sections.append(_missing_section("Missing expected devices", self.missing_expected))
        return "\n\n".join(sections)


def flow_observations_to_devices(
    flows: Iterable[FlowObservation | dict[str, Any]],
    endpoint: FlowEndpoint = "src",
) -> tuple[DeviceRecord, ...]:
    """Turn flow observations into ``DeviceRecord`` endpoint evidence."""
    devices: list[DeviceRecord] = []
    for flow in (_flow(record) for record in flows):
        if endpoint in {"src", "both"}:
            devices.append(_flow_device(flow, "src"))
        if endpoint in {"dst", "both"}:
            devices.append(_flow_device(flow, "dst"))
    return tuple(devices)


def load_flow_devices(
    path: str | Path,
    *,
    scope: FlowDeviceScope = "internal",
    exclude_exporters: bool = True,
    include_external_peers: bool = False,
    known_infrastructure: Iterable[str] = (),
    customer_hosts: Iterable[str] = (),
    internal_networks: Iterable[str] = (),
) -> tuple[DeviceRecord, ...]:
    """Load collector JSONL and return classified flow endpoint devices."""
    with Path(path).open(encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    return flow_records_to_devices(
        records,
        scope=scope,
        exclude_exporters=exclude_exporters,
        include_external_peers=include_external_peers,
        known_infrastructure=known_infrastructure,
        customer_hosts=customer_hosts,
        internal_networks=internal_networks,
    )


def flow_records_to_devices(
    records: Iterable[DeviceRecord | dict[str, Any]],
    *,
    scope: FlowDeviceScope = "internal",
    exclude_exporters: bool = True,
    include_external_peers: bool = False,
    known_infrastructure: Iterable[str] = (),
    customer_hosts: Iterable[str] = (),
    internal_networks: Iterable[str] = (),
) -> tuple[DeviceRecord, ...]:
    """Classify and filter flow endpoint device records before reconciliation."""
    devices: list[DeviceRecord] = []
    seen_hosts: set[str] = set()
    for record in records:
        device = _device_record(record)
        flow_class = classify_flow_device(
            device,
            known_infrastructure=known_infrastructure,
            customer_hosts=customer_hosts,
            internal_networks=internal_networks,
        )
        if not _include_flow_class(
            flow_class,
            scope,
            exclude_exporters=exclude_exporters,
            include_external_peers=include_external_peers,
        ):
            continue

        host_key = _normalize_host(device.host) if device.host else device.label()
        if host_key in seen_hosts:
            continue
        seen_hosts.add(host_key)
        devices.append(_device_with_flow_class(device, flow_class))
    return tuple(devices)


def classify_flow_device(
    record: DeviceRecord | dict[str, Any],
    *,
    known_infrastructure: Iterable[str] = (),
    customer_hosts: Iterable[str] = (),
    internal_networks: Iterable[str] = (),
) -> FlowDeviceClass:
    """Classify one flow endpoint as internal, external, exporter, or ignored."""
    device = _device_record(record)
    host = _normalize_host(device.host) if device.host else ""
    metadata = device.metadata or {}
    exporter = _string(metadata.get("exporter"))

    if exporter and _same_host(host, exporter):
        return "exporter"
    if _host_in_values(host, known_infrastructure):
        return "known_infrastructure"
    if _host_in_values(host, customer_hosts):
        return "customer_endpoint"
    if _host_in_networks(host, internal_networks):
        return "private_internal"
    if _is_ignored_peer_host(host):
        return "ignored_peer"
    if _is_private_host(host):
        return "unknown_internal"
    if metadata.get("direction") in {"src", "dst"}:
        return "public_external"
    return "ignored_peer"


def apply_flow_recon_policy(
    report: ReconciliationReport,
    *,
    policy: Mapping[FlowDeviceClass, FlowReconAction] = FLOW_RECON_POLICY,
) -> FlowReconPolicyReport:
    """Bucket a device reconciliation report into operator-facing flow findings."""
    matched_customer_endpoints: list[FlowReconFinding] = []
    reported: list[FlowReconFinding] = []
    infrastructure: list[FlowReconFinding] = []
    external_peers: list[FlowReconFinding] = []
    ignored_peers: list[FlowReconFinding] = []

    for match in report.matches:
        _route_flow_finding(
            _flow_finding(match.observed, policy, expected=match.expected),
            matched_customer_endpoints,
            reported,
            infrastructure,
            external_peers,
            ignored_peers,
        )

    for device in report.unknown_observed:
        _route_flow_finding(
            _flow_finding(device, policy),
            matched_customer_endpoints,
            reported,
            infrastructure,
            external_peers,
            ignored_peers,
        )

    return FlowReconPolicyReport(
        matched_customer_endpoints=_sorted_findings(matched_customer_endpoints),
        unknown_internal_hosts=_sorted_findings(reported),
        infrastructure=_sorted_findings(infrastructure),
        external_peers=_sorted_findings(external_peers),
        ignored_peers=_sorted_findings(ignored_peers),
        missing_expected=_sorted_devices(report.missing_expected),
    )


def flow_observations_to_attachments(
    flows: Iterable[FlowObservation | dict[str, Any]],
    endpoint: FlowEndpoint = "src",
) -> tuple[AttachmentRecord, ...]:
    """Turn flow observations into topology attachment evidence."""
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
    """Find the strongest flow observation for a target host or identifier."""
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
        elif _identifier_matches(target, flow.src_identifiers):
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
        elif _identifier_matches(target, flow.dst_identifiers):
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


def reconcile_flow_envelope(
    expected: FlowExpectation | dict[str, Any],
    flows: Iterable[FlowObservation | dict[str, Any]],
) -> FlowEnvelopeReport:
    expectation = _expectation(expected)
    flow_records = tuple(_flow(record) for record in flows)
    resolution = resolve_flow_target(expectation.target, flow_records)

    if not resolution:
        return FlowEnvelopeReport(
            decision="block_operation",
            identity_confidence=0,
            topology_confidence=0,
            health_score=0,
            action_safety=0,
            summary=f"{expectation.target} was not observed in flow data",
            suggested_cause="target_not_observed",
            action_safety_reason="cannot prove the operation target from flow data",
            evidence=(),
        )

    identity_confidence = _identity_confidence(resolution)
    topology_confidence = _topology_confidence(expectation, resolution)
    evidence = tuple(
        _check_signal(name, spec, _observed_signal(resolution.observation, name))
        for name, spec in expectation.envelope.items()
    )
    health_score = _health_score(evidence)
    action_safety = min(identity_confidence, topology_confidence, health_score)
    decision = _decision(identity_confidence, topology_confidence, health_score)
    suggested_cause = _suggested_cause(evidence, topology_confidence)

    return FlowEnvelopeReport(
        decision=decision,
        identity_confidence=identity_confidence,
        topology_confidence=topology_confidence,
        health_score=health_score,
        action_safety=action_safety,
        summary=_summary(decision, suggested_cause),
        suggested_cause=suggested_cause,
        action_safety_reason=_action_safety_reason(decision, suggested_cause),
        evidence=evidence,
        resolution=resolution,
    )


def _flow(record: FlowObservation | dict[str, Any]) -> FlowObservation:
    if isinstance(record, FlowObservation):
        return record
    return FlowObservation(**record)


def _expectation(record: FlowExpectation | dict[str, Any]) -> FlowExpectation:
    if isinstance(record, FlowExpectation):
        return record
    return FlowExpectation(**dict(record))


def _device_record(record: DeviceRecord | dict[str, Any]) -> DeviceRecord:
    if isinstance(record, DeviceRecord):
        return record
    values = dict(record)
    values["identifiers"] = tuple(values.get("identifiers", ()))
    values["metadata"] = dict(values.get("metadata") or {})
    return DeviceRecord(**values)


def _device_with_flow_class(
    device: DeviceRecord,
    flow_class: FlowDeviceClass,
) -> DeviceRecord:
    return DeviceRecord(
        name=device.name,
        host=device.host,
        mac=device.mac,
        serial=device.serial,
        vendor=device.vendor,
        platform=device.platform,
        source=device.source,
        identifiers=tuple(device.identifiers),
        metadata={**device.metadata, "flow_class": flow_class},
    )


def _flow_finding(
    device: DeviceRecord,
    policy: Mapping[FlowDeviceClass, FlowReconAction],
    *,
    expected: DeviceRecord | None = None,
) -> FlowReconFinding:
    flow_class = _flow_class(device)
    action = policy.get(flow_class, "report")
    return FlowReconFinding(
        host=device.host or device.label(),
        flow_class=flow_class,
        action=action,
        summary=_flow_finding_summary(device),
        device=device,
        expected=expected,
        score=_flow_match_score(device, expected) if expected else None,
    )


def _flow_match_score(device: DeviceRecord, expected: DeviceRecord) -> int:
    shared_keys = device.keys() & expected.keys()
    if any(key.startswith(("mac:", "serial:")) for key in shared_keys):
        return 100
    if any(key.startswith("host:") for key in shared_keys):
        return 95
    if any(key.startswith("name:") for key in shared_keys):
        return 80
    if shared_keys:
        return 75
    return 0


def _route_flow_finding(
    finding: FlowReconFinding,
    matched_customer_endpoints: list[FlowReconFinding],
    reported: list[FlowReconFinding],
    infrastructure: list[FlowReconFinding],
    external_peers: list[FlowReconFinding],
    ignored_peers: list[FlowReconFinding],
) -> None:
    if finding.action == "match_or_score":
        matched_customer_endpoints.append(finding)
    elif finding.action == "report":
        reported.append(finding)
    elif finding.action == "infrastructure":
        infrastructure.append(finding)
    elif finding.flow_class == "public_external":
        external_peers.append(finding)
    else:
        ignored_peers.append(finding)


def _sorted_findings(findings: Iterable[FlowReconFinding]) -> tuple[FlowReconFinding, ...]:
    return tuple(sorted(findings, key=_finding_sort_key))


def _sorted_devices(devices: Iterable[DeviceRecord]) -> tuple[DeviceRecord, ...]:
    return tuple(sorted(devices, key=_device_sort_key))


def _finding_sort_key(finding: FlowReconFinding) -> tuple[str, str, str]:
    return (_normalize_host(finding.host), finding.flow_class, finding.action)


def _device_sort_key(device: DeviceRecord) -> tuple[str, str]:
    return (_normalize_host(device.host or device.label()), device.label().lower())


def _flow_class(device: DeviceRecord) -> FlowDeviceClass:
    value = device.metadata.get("flow_class")
    if value in FLOW_RECON_POLICY:
        return value
    return "unknown_internal"


def _flow_finding_summary(device: DeviceRecord) -> str:
    metadata = device.metadata or {}
    host = device.host or device.label()
    summary = host
    exporter = _string(metadata.get("exporter"))
    if exporter:
        summary = f"{summary} seen via exporter {exporter}"
    parts = []
    interface = _flow_interface_label(metadata)
    if interface:
        parts.append(interface)
    traffic = _flow_traffic_label(metadata)
    if traffic:
        parts.append(traffic)
    if parts:
        summary = f"{summary}, {', '.join(parts)}"
    return summary


def _flow_interface_value(metadata: dict[str, Any]) -> str | None:
    direction = metadata.get("direction")
    interface = _nonzero(metadata.get("interface_index"))
    input_interface = _nonzero(metadata.get("input_interface_index"))
    output_interface = _nonzero(metadata.get("output_interface_index"))

    if interface:
        return interface
    if direction == "src" and output_interface:
        return output_interface
    if direction == "dst" and input_interface:
        return input_interface
    return None


def _flow_interface_label(metadata: dict[str, Any]) -> str | None:
    direction = metadata.get("direction")
    interface = _nonzero(metadata.get("interface_index"))
    input_interface = _nonzero(metadata.get("input_interface_index"))
    output_interface = _nonzero(metadata.get("output_interface_index"))

    if interface:
        return f"interface {interface}"
    if direction == "src" and output_interface:
        return f"output interface {output_interface}"
    if direction == "dst" and input_interface:
        return f"input interface {input_interface}"
    return None


def _flow_traffic_label(metadata: dict[str, Any]) -> str | None:
    peer = _string(metadata.get("peer_host"))
    if not peer:
        return None

    src_port = _int(metadata.get("src_port"))
    dst_port = _int(metadata.get("dst_port"))
    if dst_port in SERVICE_NAMES:
        return f"{SERVICE_NAMES[dst_port]} to {peer}"
    if src_port in SERVICE_NAMES:
        return f"{SERVICE_NAMES[src_port]} from {peer}"
    if dst_port:
        return f"port {dst_port} to {peer}"
    if src_port:
        return f"port {src_port} from {peer}"
    return f"peer {peer}"


def _finding_section(
    title: str,
    findings: tuple[FlowReconFinding, ...],
    *,
    use_summary: bool = False,
    detail: str | None = None,
) -> str:
    lines = [f"{title}:"]
    for finding in findings:
        if detail:
            lines.append(f"- {_finding_detail(finding, detail)}")
        else:
            lines.append(f"- {finding.summary if use_summary else finding.host}")
    return "\n".join(lines)


def _finding_detail(finding: FlowReconFinding, detail: str) -> str:
    metadata = finding.device.metadata or {}
    parts = [finding.host]
    if detail == "matched" and finding.score is not None:
        parts.append(f"score={finding.score}")
    if finding.device.source:
        parts.append(f"source={finding.device.source}")
    exporter = _string(metadata.get("exporter"))
    if exporter:
        parts.append(f"exporter={exporter}")
    interface = _flow_interface_value(metadata)
    if interface:
        parts.append(f"interface={interface}")
    return " ".join(parts)


def _missing_section(title: str, devices: tuple[DeviceRecord, ...]) -> str:
    lines = [f"{title}:"]
    for device in devices:
        lines.append(f"- {device.label()}")
    return "\n".join(lines)


def _flow_device(flow: FlowObservation, direction: Literal["src", "dst"]) -> DeviceRecord:
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


def _identifier_matches(target: str, identifiers: tuple[str, ...]) -> bool:
    value = target.strip().lower()
    for identifier in identifiers:
        candidate = identifier.strip().lower()
        if candidate == value or candidate.endswith(f"/{value}"):
            return True
    return False


def _include_flow_class(
    flow_class: FlowDeviceClass,
    scope: FlowDeviceScope,
    *,
    exclude_exporters: bool,
    include_external_peers: bool,
) -> bool:
    if exclude_exporters and flow_class == "exporter":
        return False
    if scope == "external":
        return flow_class == "public_external"
    if scope == "ignored":
        return flow_class == "ignored_peer"
    if scope == "all":
        return True
    if flow_class == "ignored_peer":
        return False
    if flow_class == "public_external":
        return scope == "internal" and include_external_peers
    if scope == "internal":
        return flow_class in {
            "private_internal",
            "known_infrastructure",
            "customer_endpoint",
            "unknown_internal",
            "exporter",
        }
    if scope == "managed":
        return flow_class in {"known_infrastructure", "customer_endpoint", "exporter"}
    if scope == "customer":
        return flow_class == "customer_endpoint"
    if scope == "infrastructure":
        return flow_class in {"known_infrastructure", "exporter"}
    if scope == "unknown_internal":
        return flow_class == "unknown_internal"
    return False


def _host_in_values(host: str, values: Iterable[str]) -> bool:
    return any(_same_host(host, value) for value in values)


def _host_in_networks(host: str, networks: Iterable[str]) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    for network in networks:
        try:
            if address in ipaddress.ip_network(network, strict=False):
                return True
        except ValueError:
            continue
    return False


def _is_private_host(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_link_local or address.is_loopback


def _is_ignored_peer_host(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    if (
        address.is_unspecified
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or host == "255.255.255.255"
    ):
        return True
    if isinstance(address, ipaddress.IPv4Address) and host.endswith(".255"):
        return True
    return False


def _string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _nonzero(value: Any) -> str | None:
    number = _int(value)
    if number:
        return str(number)
    if isinstance(value, str) and value.strip() and value.strip() != "0":
        return value.strip()
    return None


def _identity_confidence(resolution: FlowTargetResolution) -> int:
    if resolution.confidence == "medium_high":
        return 90
    return 75


def _topology_confidence(
    expected: FlowExpectation,
    resolution: FlowTargetResolution,
) -> int:
    score = 100
    if expected.network_device and (
        expected.network_device.strip().lower()
        != resolution.network_device.strip().lower()
    ):
        score -= 50
    if expected.interface and (
        not resolution.interface
        or expected.interface.strip().lower() != resolution.interface.strip().lower()
    ):
        score -= 50
    return max(score, 0)


def _observed_signal(flow: FlowObservation, name: str) -> Any:
    if name in flow.metadata:
        return flow.metadata[name]
    for alias in _SIGNAL_ALIASES.get(name, ()):
        if alias in flow.metadata:
            return flow.metadata[alias]
    return getattr(flow, name, None)


def _check_signal(name: str, spec: Any, observed: Any) -> FlowSignalCheck:
    expected = _signal_spec(spec)
    severity = expected.get("severity", "medium")
    if observed is None:
        return FlowSignalCheck(
            name,
            "missing",
            _expected_label(expected),
            None,
            severity,
            50,
            f"{name} was not observed",
        )

    ok = _signal_ok(expected, observed)
    return FlowSignalCheck(
        name,
        "inside_envelope" if ok else "out_of_envelope",
        _expected_label(expected),
        observed,
        severity,
        100 if ok else 0,
        f"{name} is inside expected envelope"
        if ok
        else f"{name} is outside expected envelope",
    )


def _signal_spec(spec: Any) -> dict[str, Any]:
    if isinstance(spec, dict):
        if spec.get("near_zero"):
            return {**spec, "max": spec.get("max", 0)}
        return dict(spec)
    if isinstance(spec, (tuple, list)) and len(spec) == 2:
        return {"min": spec[0], "max": spec[1]}
    return {"equals": spec}


def _signal_ok(spec: dict[str, Any], observed: Any) -> bool:
    if "equals" in spec:
        if observed == spec["equals"]:
            return True
        try:
            return float(observed) == float(spec["equals"])
        except (TypeError, ValueError):
            return False

    try:
        value = float(observed)
    except (TypeError, ValueError):
        return False

    minimum = spec.get("min")
    maximum = spec.get("max")
    if minimum is not None and value < float(minimum):
        return False
    if maximum is not None and value > float(maximum):
        return False
    return True


def _expected_label(spec: dict[str, Any]) -> Any:
    if "equals" in spec:
        return spec["equals"]
    if "min" in spec and "max" in spec:
        return f"{spec['min']}..{spec['max']}"
    if "min" in spec:
        return f">= {spec['min']}"
    if "max" in spec:
        return f"<= {spec['max']}"
    return spec


def _health_score(evidence: tuple[FlowSignalCheck, ...]) -> int:
    if not evidence:
        return 100
    return round(sum(check.score for check in evidence) / len(evidence))


def _decision(identity: int, topology: int, health: int) -> str:
    if identity < 50:
        return "block_operation"
    if topology < 60 or health < 50:
        return "investigate_first"
    if topology < 80 or health < 80:
        return "allow_with_confirmation"
    return "safe"


def _suggested_cause(
    evidence: tuple[FlowSignalCheck, ...],
    topology_confidence: int,
) -> str | None:
    failed = {
        check.signal
        for check in evidence
        if check.status in {"out_of_envelope", "missing"}
    }
    if topology_confidence < 60:
        return "topology_mismatch"
    if failed & WIRELESS_SIGNALS:
        return "wireless_or_physical_layer_issue"
    if failed & TRANSPORT_SIGNALS:
        return "interface_or_transport_issue"
    if failed & THROUGHPUT_SIGNALS:
        return "traffic_anomaly"
    return None


def _summary(decision: str, cause: str | None) -> str:
    if decision == "safe":
        return "identity, topology, and health are inside the expected envelope"
    if cause == "wireless_or_physical_layer_issue":
        return "identity matches, but wireless link quality is degraded"
    if cause == "interface_or_transport_issue":
        return "identity matches, but interface health is degraded"
    if cause == "topology_mismatch":
        return "identity matches, but topology does not match expectation"
    if cause == "traffic_anomaly":
        return "identity matches, but traffic is outside the expected envelope"
    return "identity matches, but observed signals need review"


def _action_safety_reason(decision: str, cause: str | None) -> str:
    if decision == "safe":
        return "observed state is inside the expected envelope"
    if cause == "topology_mismatch":
        return "confirm target location before config changes"
    return "do not push config changes while the link is unstable"


def _normalize_host(host: str) -> str:
    value = host.strip().lower()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return value


WIRELESS_SIGNALS = frozenset(
    {
        "rssi",
        "ccq",
        "noise_floor",
        "snr",
        "signal",
        "signal_chain",
        "disconnect_count",
    }
)

TRANSPORT_SIGNALS = frozenset(
    {
        "mtu",
        "link_speed",
        "duplex",
        "tx_errors",
        "rx_errors",
        "tx_errors_delta",
        "rx_errors_delta",
        "drops",
        "crc_errors",
        "fcs_errors",
        "flapping_count",
        "bridge_stp_state",
        "queue_drops",
    }
)

THROUGHPUT_SIGNALS = frozenset(
    {
        "traffic_mbps",
        "throughput_mbps",
    }
)

_SIGNAL_ALIASES = {
    "traffic_mbps": ("throughput_mbps", "mbps"),
    "rx_errors": ("rx_errors_delta",),
    "tx_errors": ("tx_errors_delta",),
}

SERVICE_NAMES = {
    22: "SSH",
    53: "DNS",
    80: "HTTP",
    123: "NTP",
    443: "HTTPS",
    8291: "Winbox",
}
