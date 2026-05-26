from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .model import Operation
from .reconcile import DeviceRecord


@dataclass(frozen=True)
class AttachmentRecord:
    device: DeviceRecord
    network_device: str
    interface: str
    source: str | None = None
    scope: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def keys(self) -> frozenset[str]:
        return self.device.keys()

    def location_key(self) -> tuple[str, str, str | None]:
        return (
            self.network_device.strip().lower(),
            self.interface.strip().lower(),
            self.scope.strip().lower() if self.scope else None,
        )

    def location_label(self) -> str:
        location = f"{self.network_device} {self.interface}"
        if self.scope:
            return f"{location} ({self.scope})"
        return location

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device.to_dict(),
            "network_device": self.network_device,
            "interface": self.interface,
            "source": self.source,
            "scope": self.scope,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class AttachmentMatch:
    expected: AttachmentRecord
    observed: AttachmentRecord
    keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected": self.expected.to_dict(),
            "observed": self.observed.to_dict(),
            "keys": list(self.keys),
        }


@dataclass(frozen=True)
class AttachmentMove:
    expected: AttachmentRecord
    observed: AttachmentRecord
    keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected": self.expected.to_dict(),
            "observed": self.observed.to_dict(),
            "keys": list(self.keys),
        }


@dataclass(frozen=True)
class DuplicateAttachment:
    key: str
    observations: tuple[AttachmentRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "observations": [
                observation.to_dict() for observation in self.observations
            ],
        }


@dataclass(frozen=True)
class AttachmentReconciliationReport:
    matches: tuple[AttachmentMatch, ...]
    moved: tuple[AttachmentMove, ...]
    unknown_observed: tuple[AttachmentRecord, ...]
    missing_expected: tuple[AttachmentRecord, ...]
    duplicate_observed: tuple[DuplicateAttachment, ...] = ()

    @property
    def ok(self) -> bool:
        return not (
            self.moved
            or self.unknown_observed
            or self.missing_expected
            or self.duplicate_observed
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "matches": [match.to_dict() for match in self.matches],
            "moved": [move.to_dict() for move in self.moved],
            "unknown_observed": [
                attachment.to_dict() for attachment in self.unknown_observed
            ],
            "missing_expected": [
                attachment.to_dict() for attachment in self.missing_expected
            ],
            "duplicate_observed": [
                duplicate.to_dict() for duplicate in self.duplicate_observed
            ],
        }


@dataclass(frozen=True)
class TopologyPreflightReport:
    operation: str
    target: Any
    interface: str | None
    reconciliation: AttachmentReconciliationReport
    risks: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.risks and self.reconciliation.ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "operation": self.operation,
            "target": self.target,
            "interface": self.interface,
            "risks": list(self.risks),
            "reconciliation": self.reconciliation.to_dict(),
        }


def reconcile_attachments(
    expected: Iterable[AttachmentRecord | dict[str, Any]],
    observed: Iterable[AttachmentRecord | dict[str, Any]],
) -> AttachmentReconciliationReport:
    expected_records = tuple(_attachment(record) for record in expected)
    observed_records = tuple(_attachment(record) for record in observed)
    expected_index = _index(expected_records)

    matches: list[AttachmentMatch] = []
    moved: list[AttachmentMove] = []
    matched_expected_indexes: set[int] = set()
    unknown_observed: list[AttachmentRecord] = []

    for observed_record in observed_records:
        observed_keys = observed_record.keys()
        candidates = {
            expected_index[key]
            for key in observed_keys
            if key in expected_index
        }
        if not candidates:
            unknown_observed.append(observed_record)
            continue

        expected_index_value = min(candidates)
        expected_record = expected_records[expected_index_value]
        matched_expected_indexes.add(expected_index_value)
        common_keys = tuple(sorted(expected_record.keys() & observed_keys))
        if expected_record.location_key() == observed_record.location_key():
            matches.append(
                AttachmentMatch(expected_record, observed_record, common_keys)
            )
        else:
            moved.append(AttachmentMove(expected_record, observed_record, common_keys))

    missing_expected = tuple(
        record
        for index, record in enumerate(expected_records)
        if index not in matched_expected_indexes
    )

    return AttachmentReconciliationReport(
        matches=tuple(matches),
        moved=tuple(moved),
        unknown_observed=tuple(unknown_observed),
        missing_expected=missing_expected,
        duplicate_observed=_duplicate_observations(observed_records),
    )


def preflight_interface_operation(
    operation: Operation,
    expected: Iterable[AttachmentRecord | dict[str, Any]],
    observed: Iterable[AttachmentRecord | dict[str, Any]],
) -> TopologyPreflightReport:
    interface = _operation_interface(operation)
    expected_records = tuple(_attachment(record) for record in expected)
    observed_records = tuple(_attachment(record) for record in observed)

    if not isinstance(operation.target, str) or not interface:
        reconciliation = reconcile_attachments((), ())
        return TopologyPreflightReport(
            operation=operation.name,
            target=operation.target,
            interface=interface,
            reconciliation=reconciliation,
            risks=("operation does not identify a target interface",),
        )

    scoped_expected = tuple(
        record
        for record in expected_records
        if _same_location(record, operation.target, interface)
    )
    scoped_expected_keys = {
        key for record in scoped_expected for key in record.keys()
    }
    scoped_observed = tuple(
        record
        for record in observed_records
        if _same_location(record, operation.target, interface)
        or bool(record.keys() & scoped_expected_keys)
    )

    reconciliation = reconcile_attachments(scoped_expected, scoped_observed)
    return TopologyPreflightReport(
        operation=operation.name,
        target=operation.target,
        interface=interface,
        reconciliation=reconciliation,
        risks=_risks(reconciliation),
    )


def _index(records: tuple[AttachmentRecord, ...]) -> dict[str, int]:
    index: dict[str, int] = {}
    for record_index, record in enumerate(records):
        for key in record.keys():
            index.setdefault(key, record_index)
    return index


def _attachment(record: AttachmentRecord | dict[str, Any]) -> AttachmentRecord:
    if isinstance(record, AttachmentRecord):
        return record
    values = dict(record)
    device = values.get("device")
    if isinstance(device, dict):
        values["device"] = DeviceRecord(**device)
    return AttachmentRecord(**values)


def _duplicate_observations(
    observed: tuple[AttachmentRecord, ...],
) -> tuple[DuplicateAttachment, ...]:
    by_key: dict[str, list[AttachmentRecord]] = {}
    for record in observed:
        for key in record.keys():
            by_key.setdefault(key, []).append(record)

    duplicates = []
    for key, records in sorted(by_key.items()):
        locations = {record.location_key() for record in records}
        if len(locations) > 1:
            duplicates.append(DuplicateAttachment(key, tuple(records)))
    return tuple(duplicates)


def _operation_interface(operation: Operation) -> str | None:
    name = operation.params.get("name")
    if isinstance(name, str) and name.strip():
        return name
    match = operation.params.get("match")
    if isinstance(match, dict):
        for key in ("interface", "name", "port"):
            value = match.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _same_location(
    record: AttachmentRecord,
    network_device: str,
    interface: str,
) -> bool:
    return (
        record.network_device.strip().lower() == network_device.strip().lower()
        and record.interface.strip().lower() == interface.strip().lower()
    )


def _risks(report: AttachmentReconciliationReport) -> tuple[str, ...]:
    risks = []
    for move in report.moved:
        risks.append(
            f"{move.expected.device.label()} expected on "
            f"{move.expected.location_label()} but observed on "
            f"{move.observed.location_label()}"
        )
    for attachment in report.unknown_observed:
        risks.append(
            f"unknown live device {attachment.device.label()} observed on "
            f"{attachment.location_label()}"
        )
    for attachment in report.missing_expected:
        risks.append(
            f"expected device {attachment.device.label()} was not observed on "
            f"{attachment.location_label()}"
        )
    for duplicate in report.duplicate_observed:
        locations = ", ".join(
            attachment.location_label() for attachment in duplicate.observations
        )
        risks.append(f"{duplicate.key} observed in multiple locations: {locations}")
    return tuple(risks)
