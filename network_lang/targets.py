from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .model import Operation
from .result import OperationResult


class TargetResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class TargetDevice:
    name: str
    url: str
    vendor: str
    platform: str
    transport: str
    executor: Any
    record: dict[str, Any] = field(default_factory=dict)

    @property
    def network_device(self) -> str:
        return self.name

    def execute(self, operation: Operation) -> OperationResult:
        return self.executor.execute(operation)

    def operation(self, operation_name: str, **params: Any) -> Operation:
        from .api import build_operation

        return build_operation(operation_name, target=self.name, **params)

    def collect_topology(self) -> OperationResult:
        return collect_topology(self)

    def preflight(
        self,
        operation: Operation | str,
        *,
        expected: Iterable[Any] = (),
        **params: Any,
    ) -> OperationResult:
        return preflight_operation(self, operation, expected=expected, **params)

    def graph(self, operation_name: str, **params: Any) -> Any:
        from .graph_client import graph_operation

        return graph_operation(self, operation_name, **params)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "vendor": self.vendor,
            "platform": self.platform,
            "transport": self.transport,
            "record": dict(self.record),
        }


def target_device(
    target: str,
    *,
    inventory: Iterable[dict[str, Any]] | None = None,
    inventory_path: str | Path | None = None,
    secure: bool | None = None,
) -> TargetDevice:
    """

    Args:
        target:
        inventory:
        inventory_path:
        secure:

    Returns:

    """
    record = resolve_target(
        target,
        inventory=inventory,
        inventory_path=inventory_path,
    )

    vendor = _normalized(record.get("vendor"), default="mikrotik")
    platform = _normalized(record.get("platform") or record.get("os"), default="routeros")
    transport = _normalized(record.get("transport"), default="rest")

    if not _is_routeros(vendor, platform, transport):
        raise TargetResolutionError(
            f"target {target!r} resolved to unsupported adapter "
            f"{vendor}/{platform}/{transport}"
        )

    return _routeros_target_device(record, target, vendor, platform, transport, secure)


def collect_topology(
    target: TargetDevice | str,
    *,
    inventory: Iterable[dict[str, Any]] | None = None,
    inventory_path: str | Path | None = None,
    secure: bool | None = None,
) -> OperationResult:
    """

    Args:
        target:
        inventory:
        inventory_path:
        secure:

    Returns:

    """
    device = _target_device(
        target,
        inventory=inventory,
        inventory_path=inventory_path,
        secure=secure,
    )

    if _is_routeros(device.vendor, device.platform, device.transport):
        from .adapters import collect_routeros_topology

        return collect_routeros_topology(
            device,
            device.name,
            network_device=device.network_device,
        )

    raise TargetResolutionError(
        f"topology collection is unsupported for "
        f"{device.vendor}/{device.platform}/{device.transport}"
    )


def preflight_operation(
    target: TargetDevice | str,
    operation: Operation | str,
    *,
    expected: Iterable[Any] = (),
    inventory: Iterable[dict[str, Any]] | None = None,
    inventory_path: str | Path | None = None,
    secure: bool | None = None,
    **params: Any,
) -> OperationResult:
    """

    Args:
        target:
        operation:
        expected:
        inventory:
        inventory_path:
        secure:
        **params:

    Returns:

    """
    device = _target_device(
        target,
        inventory=inventory,
        inventory_path=inventory_path,
        secure=secure,
    )
    operation_value = _operation_for_device(device, operation, params)

    if _is_routeros(device.vendor, device.platform, device.transport):
        from .adapters import preflight_routeros_operation

        return preflight_routeros_operation(
            device,
            operation_value,
            expected=expected,
            network_device=device.network_device,
        )

    raise TargetResolutionError(
        f"preflight is unsupported for "
        f"{device.vendor}/{device.platform}/{device.transport}"
    )


def resolve_target(
    target: str,
    *,
    inventory: Iterable[dict[str, Any]] | None = None,
    inventory_path: str | Path | None = None,
) -> dict[str, Any]:
    """

    Args:
        target:
        inventory:
        inventory_path:

    Returns:

    """
    records = tuple(inventory) if inventory is not None else load_inventory(inventory_path)
    target_value = str(target)

    for record in records:
        if _record_matches(record, target_value):
            return dict(record)

    raise TargetResolutionError(f"target {target!r} not found in inventory")


def load_inventory(inventory_path: str | Path | None = None) -> tuple[dict[str, Any], ...]:
    """

    Args:
        inventory_path:

    Returns:

    """
    path = Path(inventory_path) if inventory_path else default_inventory_path()
    try:
        with path.open() as handle:
            data = json.load(handle)
    except FileNotFoundError as error:
        raise TargetResolutionError(f"inventory file not found: {path}") from error

    if not isinstance(data, list):
        raise TargetResolutionError("inventory file must contain a list of targets")

    return tuple(record for record in data if isinstance(record, dict))


def default_inventory_path() -> Path:
    """

    Returns:

    """
    configured = os.environ.get("NETWORK_LANG_INVENTORY")
    if configured:
        return Path(configured)

    return Path.cwd() / "network_lang" / "data" / "inventory.json"


def _routeros_target_device(
    record: dict[str, Any],
    requested_target: str,
    vendor: str,
    platform: str,
    transport: str,
    secure: bool | None,
) -> TargetDevice:
    """

    Args:
        record:
        requested_target:
        vendor:
        platform:
        transport:
        secure:

    Returns:

    """
    from .adapters import RouterOSExecutor, RouterOSRestTransport
    from .adapters.rosapi import Ros

    url = _string(record.get("url"))
    if not url:
        raise TargetResolutionError(f"target {requested_target!r} does not have a URL")

    username = _string(record.get("username")) or "admin"
    password = _string(record.get("password")) or ""
    verify_tls = _bool(record.get("secure"), default=secure if secure is not None else False)

    ros = Ros(url, username, password, secure=verify_tls)
    executor = RouterOSExecutor(RouterOSRestTransport(ros))
    return TargetDevice(
        name=_string(record.get("name")) or requested_target,
        url=url,
        vendor=vendor,
        platform=platform,
        transport=transport,
        executor=executor,
        record=dict(record),
    )


def _target_device(
    target: TargetDevice | str,
    *,
    inventory: Iterable[dict[str, Any]] | None,
    inventory_path: str | Path | None,
    secure: bool | None,
) -> TargetDevice:
    """

    Args:
        target:
        inventory:
        inventory_path:
        secure:

    Returns:

    """
    if isinstance(target, TargetDevice):
        return target
    return target_device(
        target,
        inventory=inventory,
        inventory_path=inventory_path,
        secure=secure,
    )


def _operation_for_device(
    device: TargetDevice,
    operation: Operation | str,
    params: dict[str, Any],
) -> Operation:
    """

    Args:
        device:
        operation:
        params:

    Returns:

    """
    if isinstance(operation, Operation):
        if params:
            raise ValueError("operation params can only be passed with operation names")
        return operation

    return device.operation(operation, **params)


def _record_matches(record: dict[str, Any], target: str) -> bool:
    """

    Args:
        record:
        target:

    Returns:

    """
    for key in ("name", "url", "id", "host", "hostname", "address"):
        value = record.get(key)
        if value is not None and str(value) == target:
            return True
    return False


def _is_routeros(vendor: str, platform: str, transport: str) -> bool:
    """

    Args:
        vendor:
        platform:
        transport:

    Returns:

    """
    return transport == "rest" and (
        vendor in {"mikrotik", "routeros"} or platform == "routeros"
    )


def _normalized(value: Any, *, default: str) -> str:
    """

    Args:
        value:
        default:

    Returns:

    """
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return default


def _string(value: Any) -> str | None:
    """

    Args:
        value:

    Returns:

    """
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _bool(value: Any, *, default: bool) -> bool:
    """

    Args:
        value:
        default:

    Returns:

    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "on"}:
            return True
        if normalized in {"false", "no", "n", "0", "off"}:
            return False
    return default
