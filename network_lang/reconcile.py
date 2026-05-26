from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class DeviceRecord:
    name: str | None = None
    host: str | None = None
    mac: str | None = None
    serial: str | None = None
    vendor: str | None = None
    platform: str | None = None
    source: str | None = None
    identifiers: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def keys(self) -> frozenset[str]:
        keys = set()
        for key in self.identifiers:
            if key.strip():
                keys.add(key.strip().lower())
        if self.name:
            keys.add(f"name:{self.name.strip().lower()}")
        if self.host:
            keys.add(f"host:{_normalize_host(self.host)}")
        if self.mac:
            keys.add(f"mac:{_normalize_mac(self.mac)}")
        if self.serial:
            keys.add(f"serial:{self.serial.strip().lower()}")
        return frozenset(keys)

    def label(self) -> str:
        return self.name or self.host or self.mac or self.serial or "<unknown>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "host": self.host,
            "mac": self.mac,
            "serial": self.serial,
            "vendor": self.vendor,
            "platform": self.platform,
            "source": self.source,
            "identifiers": list(self.identifiers),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class DeviceMatch:
    expected: DeviceRecord
    observed: DeviceRecord
    keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected": self.expected.to_dict(),
            "observed": self.observed.to_dict(),
            "keys": list(self.keys),
        }


@dataclass(frozen=True)
class ReconciliationReport:
    matches: tuple[DeviceMatch, ...]
    unknown_observed: tuple[DeviceRecord, ...]
    missing_expected: tuple[DeviceRecord, ...]

    @property
    def ok(self) -> bool:
        return not self.unknown_observed and not self.missing_expected

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "matches": [match.to_dict() for match in self.matches],
            "unknown_observed": [
                device.to_dict() for device in self.unknown_observed
            ],
            "missing_expected": [
                device.to_dict() for device in self.missing_expected
            ],
        }


def reconcile_devices(
    expected: Iterable[DeviceRecord | dict[str, Any]],
    observed: Iterable[DeviceRecord | dict[str, Any]],
) -> ReconciliationReport:
    """

    Args:
        expected:
        observed:

    Returns:

    """
    expected_records = tuple(_device(record) for record in expected)
    observed_records = tuple(_device(record) for record in observed)
    expected_index = _index(expected_records)

    matches: list[DeviceMatch] = []
    matched_expected_indexes: set[int] = set()
    unknown_observed: list[DeviceRecord] = []

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
        matches.append(
            DeviceMatch(
                expected=expected_record,
                observed=observed_record,
                keys=tuple(sorted(expected_record.keys() & observed_keys)),
            )
        )

    missing_expected = tuple(
        record
        for index, record in enumerate(expected_records)
        if index not in matched_expected_indexes
    )

    return ReconciliationReport(
        matches=tuple(matches),
        unknown_observed=tuple(unknown_observed),
        missing_expected=missing_expected,
    )


def _index(records: tuple[DeviceRecord, ...]) -> dict[str, int]:
    """

    Args:
        records:

    Returns:

    """
    index: dict[str, int] = {}
    for record_index, record in enumerate(records):
        for key in record.keys():
            index.setdefault(key, record_index)
    return index


def _device(record: DeviceRecord | dict[str, Any]) -> DeviceRecord:
    """

    Args:
        record:

    Returns:

    """
    if isinstance(record, DeviceRecord):
        return record
    return DeviceRecord(**record)


def _normalize_host(host: str) -> str:
    """

    Args:
        host:

    Returns:

    """
    value = host.strip().lower()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return value


def _normalize_mac(mac: str) -> str:
    """

    Args:
        mac:

    Returns:

    """
    value = re.sub(r"[^0-9a-fA-F]", "", mac).lower()
    if len(value) == 12:
        return ":".join(value[index : index + 2] for index in range(0, 12, 2))
    return mac.strip().lower()
