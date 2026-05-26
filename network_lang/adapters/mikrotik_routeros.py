from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from ..api import build_operation
from ..model import Operation
from ..reconcile import DeviceRecord
from ..result import OperationResult, ResultError
from ..topology import (
    AttachmentRecord,
    InterfaceStateRecord,
    preflight_interface_operation,
)


ROUTEROS_ADAPTER = {
    "vendor": "mikrotik",
    "platform": "routeros",
    "transport": "rest",
    "name": "routeros-rest",
}


class RouterOSTransport(Protocol):
    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        ...


class RouterOSRestTransport:
    """Execute RouterOS REST calls through a vendored Ros client instance."""

    def __init__(self, ros: Any) -> None:
        self.ros = ros

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.ros.url}{path}"
        session = self.ros.session
        method = method.upper()

        if method == "GET":
            response = session.get(url, params=params, verify=self.ros.secure)
        elif method == "PUT":
            response = session.put(url, json=body)
        elif method == "PATCH":
            response = session.patch(url, json=body)
        elif method == "POST":
            response = session.post(url, json=body)
        elif method == "DELETE":
            response = session.delete(url)
        else:
            raise ValueError(f"unsupported RouterOS REST method: {method}")

        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        if not getattr(response, "text", ""):
            return None

        data = json.loads(response.text)
        return _clean_routeros_data(data)


class RouterOSExecutor:
    def __init__(self, transport: RouterOSTransport) -> None:
        self.transport = transport

    def execute(self, operation: Operation) -> OperationResult:
        plan = plan_routeros_operation(operation)
        return self.execute_plan(operation, plan)

    def execute_plan(
        self,
        operation: Operation,
        plan: RouterOSPlan,
    ) -> OperationResult:
        if not plan.supported:
            return _result_error(
                operation,
                plan.capability,
                "UNSUPPORTED_OPERATION",
                plan.warnings[0] if plan.warnings else "operation is unsupported",
                warnings=plan.warnings,
            )

        outputs: list[Any] = []
        resolved_id: str | None = None

        try:
            for step in plan.steps:
                path = step.path
                if "<resolved-id>" in path:
                    if not resolved_id:
                        return _result_error(
                            operation,
                            plan.capability,
                            "LOOKUP_NOT_RESOLVED",
                            "operation requires a prior lookup result with an id",
                            warnings=plan.warnings,
                        )
                    path = path.replace("<resolved-id>", resolved_id)

                data = self.transport.request(
                    step.method,
                    path,
                    params=step.params,
                    body=step.body,
                )

                if step.name == "lookup":
                    lookup = _extract_single_id(data)
                    if lookup.error:
                        return _result_error(
                            operation,
                            plan.capability,
                            lookup.error.code,
                            lookup.error.message,
                            warnings=plan.warnings,
                            detail=lookup.error.detail,
                        )
                    resolved_id = lookup.resource_id
                    continue

                outputs.append(data)
        except Exception as error:
            return _result_error(
                operation,
                plan.capability,
                "ADAPTER_ERROR",
                str(error),
                warnings=plan.warnings,
            )

        data = outputs[0] if len(outputs) == 1 else outputs
        return OperationResult(
            ok=True,
            operation=operation.name,
            target=operation.target,
            capability=plan.capability,
            adapter=dict(ROUTEROS_ADAPTER),
            data=data,
            warnings=plan.warnings,
        )


def execute_routeros_operation(
    operation: Operation,
    transport: RouterOSTransport,
) -> OperationResult:
    return RouterOSExecutor(transport).execute(operation)


@dataclass(frozen=True)
class RouterOSTopologySnapshot:
    target: str
    network_device: str
    attachments: tuple[AttachmentRecord, ...]
    interface_states: tuple[InterfaceStateRecord, ...]
    raw_neighbors: Any = ()
    raw_bridge_ports: Any = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "network_device": self.network_device,
            "attachments": [
                attachment.to_dict() for attachment in self.attachments
            ],
            "interface_states": [
                state.to_dict() for state in self.interface_states
            ],
            "raw_neighbors": self.raw_neighbors,
            "raw_bridge_ports": self.raw_bridge_ports,
        }


def collect_routeros_topology(
    executor: RouterOSExecutor,
    target: str,
    network_device: str | None = None,
) -> OperationResult:
    """Collect read-only RouterOS topology observations into a single snapshot."""

    operation = build_operation("network.topology.snapshot.observe", target=target)
    observed_device = network_device or target

    neighbors_result = executor.execute(
        build_operation("network.neighbors.list", target=target)
    )
    if not neighbors_result.ok:
        return _composed_error(
            operation,
            neighbors_result,
            "failed to collect RouterOS neighbors",
        )

    bridge_ports_result = executor.execute(
        build_operation("network.bridge.ports.list", target=target)
    )
    if not bridge_ports_result.ok:
        return _composed_error(
            operation,
            bridge_ports_result,
            "failed to collect RouterOS bridge ports",
        )

    neighbors = _row_sequence(neighbors_result.data)
    bridge_ports = _row_sequence(bridge_ports_result.data)
    snapshot = RouterOSTopologySnapshot(
        target=target,
        network_device=observed_device,
        attachments=routeros_neighbors_to_attachments(neighbors, observed_device),
        interface_states=routeros_bridge_ports_to_interface_states(
            bridge_ports,
            observed_device,
        ),
        raw_neighbors=neighbors_result.data,
        raw_bridge_ports=bridge_ports_result.data,
    )
    return OperationResult(
        ok=True,
        operation=operation.name,
        target=target,
        capability="supported_via_composition",
        adapter=dict(ROUTEROS_ADAPTER),
        data=snapshot,
        warnings=(*neighbors_result.warnings, *bridge_ports_result.warnings),
    )


def preflight_routeros_operation(
    executor: RouterOSExecutor,
    operation: Operation,
    expected: Iterable[AttachmentRecord | dict[str, Any]] = (),
    network_device: str | None = None,
) -> OperationResult:
    """Collect RouterOS topology and preflight an operation against it."""

    if not isinstance(operation.target, str) or not operation.target.strip():
        return _result_error(
            operation,
            "preflight_unavailable",
            "TARGET_REQUIRED",
            "RouterOS preflight requires a string target",
        )

    snapshot_result = collect_routeros_topology(
        executor,
        operation.target,
        network_device=network_device,
    )
    if not snapshot_result.ok:
        return OperationResult(
            ok=False,
            operation=operation.name,
            target=operation.target,
            capability="preflight_unavailable",
            adapter=dict(ROUTEROS_ADAPTER),
            warnings=snapshot_result.warnings,
            error=snapshot_result.error,
        )

    snapshot = snapshot_result.data
    preflight_operation = (
        _operation_with_target(operation, network_device)
        if network_device
        else operation
    )
    report = preflight_interface_operation(
        preflight_operation,
        expected,
        snapshot.attachments,
        snapshot.interface_states,
    )
    return OperationResult(
        ok=report.ok,
        operation=operation.name,
        target=operation.target,
        capability="preflight",
        adapter=dict(ROUTEROS_ADAPTER),
        data=report,
        warnings=snapshot_result.warnings,
        error=ResultError(
            "PREFLIGHT_RISK",
            "preflight found topology risks",
            detail=report.to_dict(),
        )
        if not report.ok
        else None,
    )


def routeros_neighbors_to_devices(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> tuple[DeviceRecord, ...]:
    return tuple(_neighbor_device(row) for row in rows)


def routeros_neighbors_to_attachments(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    network_device: str,
) -> tuple[AttachmentRecord, ...]:
    attachments = []
    for row in rows:
        interface = _neighbor_interface(row)
        if interface:
            attachments.append(
                AttachmentRecord(
                    device=_neighbor_device(row),
                    network_device=network_device,
                    interface=interface,
                    source="routeros:/ip/neighbor",
                    metadata=_metadata(row),
                )
            )
    return tuple(attachments)


def routeros_arp_to_devices(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> tuple[DeviceRecord, ...]:
    return tuple(_arp_device(row) for row in rows)


def routeros_arp_to_attachments(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    network_device: str,
) -> tuple[AttachmentRecord, ...]:
    attachments = []
    for row in rows:
        interface = _string(row.get("interface"))
        if interface:
            attachments.append(
                AttachmentRecord(
                    device=_arp_device(row),
                    network_device=network_device,
                    interface=interface,
                    source="routeros:/ip/arp",
                    metadata=_metadata(row),
                )
            )
    return tuple(attachments)


def routeros_bridge_hosts_to_attachments(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    network_device: str,
) -> tuple[AttachmentRecord, ...]:
    attachments = []
    for row in rows:
        interface = _string(row.get("interface"))
        mac = _string(row.get("mac_address") or row.get("mac-address"))
        if interface and mac:
            attachments.append(
                AttachmentRecord(
                    device=DeviceRecord(
                        mac=mac,
                        source="routeros:/interface/bridge/host",
                        metadata=_metadata(row),
                    ),
                    network_device=network_device,
                    interface=interface,
                    source="routeros:/interface/bridge/host",
                    metadata=_metadata(row),
                )
            )
    return tuple(attachments)


def routeros_bridge_ports_to_interface_states(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    network_device: str,
) -> tuple[InterfaceStateRecord, ...]:
    states = []
    for row in rows:
        interface = _string(row.get("interface"))
        if interface:
            status = _string(row.get("status"))
            forwarding = _bool(row.get("forwarding"))
            inactive = _bool(row.get("inactive"))
            if inactive is None:
                inactive = _bridge_port_status_inactive(status)
            running = _bool(row.get("running"))
            if running is None:
                running = forwarding
            if running is None:
                running = _bridge_port_status_running(status)
            states.append(
                InterfaceStateRecord(
                    network_device=network_device,
                    interface=interface,
                    source="routeros:/interface/bridge/port",
                    scope=_string(row.get("bridge")),
                    disabled=_bool(row.get("disabled")),
                    inactive=inactive,
                    running=running,
                    status=status,
                    forwarding=forwarding,
                    metadata=_metadata(row),
                )
            )
    return tuple(states)


@dataclass(frozen=True)
class RouterOSPlanStep:
    name: str
    method: str
    path: str
    params: dict[str, Any] | None = None
    body: dict[str, Any] | None = None


@dataclass(frozen=True)
class RouterOSPlan:
    operation: str
    capability: str
    steps: tuple[RouterOSPlanStep, ...]
    warnings: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        return self.capability in {"supported", "supported_via_fallback"}


def plan_routeros_operation(operation: Operation) -> RouterOSPlan:
    """Translate a vendor-neutral operation into RouterOS REST API calls."""

    if operation.name == "network.system.identity.get":
        return _get(operation, "/system/identity")

    if operation.name == "network.neighbors.list":
        return _get(operation, "/ip/neighbor", _filters(operation))

    if operation.name == "network.bridge.hosts.list":
        return _get(operation, "/interface/bridge/host", _filters(operation))

    if operation.name == "network.bridge.ports.list":
        return _get(operation, "/interface/bridge/port", _filters(operation))

    if operation.name == "network.interfaces.list":
        return _get(operation, "/interface", _filters(operation))

    if operation.name == "network.interfaces.get":
        filters = _filters(operation)
        name = operation.params.get("name")
        if isinstance(name, str):
            filters["name"] = name
        return _get(operation, "/interface", filters)

    if operation.name in {"network.interfaces.disable", "network.interfaces.enable"}:
        return _toggle_by_id_or_match(
            operation,
            "/interface",
            disabled=operation.action == "disable",
        )

    if operation.name == "network.routes.list":
        return _get(operation, "/ip/route", _filters(operation))

    if operation.name == "network.routes.create":
        route = _body_map(operation, "route", "data")
        if not route:
            return _unsupported(operation, "route create requires route or data params")
        return _write(
            operation,
            "PUT",
            "/ip/route",
            _translate_keys(route, ROUTE_KEY_MAP),
        )

    if operation.name == "network.firewall.rules.list":
        return _get(operation, "/ip/firewall/filter", _filters(operation))

    if operation.name == "network.firewall.rules.create":
        rule = _body_map(operation, "rule", "data")
        if not rule:
            return _unsupported(
                operation,
                "firewall rule create requires rule or data params",
            )
        return _write(
            operation,
            "PUT",
            "/ip/firewall/filter",
            _translate_keys(rule, FIREWALL_RULE_KEY_MAP),
        )

    if operation.name == "network.addresses.list":
        return _get(operation, "/ip/address", _filters(operation))

    if operation.name == "network.addresses.create":
        address = _body_map(operation, "address", "data")
        if not address:
            return _unsupported(operation, "address create requires address or data params")
        return _write(operation, "PUT", "/ip/address", address)

    if operation.name == "network.wireless.clients.list":
        return _get(
            operation,
            "/interface/wireless/registration-table",
            _filters(operation),
        )

    return _unsupported(operation, "operation is not mapped for RouterOS")


ROUTE_KEY_MAP = {
    "dst": "dst-address",
    "dst_address": "dst-address",
    "routing_table": "routing-table",
    "table": "routing-table",
    "pref_src": "pref-src",
    "check_gateway": "check-gateway",
    "suppress_hw_offload": "suppress-hw-offload",
    "target_scope": "target-scope",
    "vrf_interface": "vrf-interface",
}

FIREWALL_RULE_KEY_MAP = {
    "src": "src-address",
    "dst": "dst-address",
    "src_address": "src-address",
    "dst_address": "dst-address",
    "src_address_list": "src-address-list",
    "dst_address_list": "dst-address-list",
    "src_port": "src-port",
    "dst_port": "dst-port",
    "in_interface": "in-interface",
    "out_interface": "out-interface",
    "in_interface_list": "in-interface-list",
    "out_interface_list": "out-interface-list",
    "connection_state": "connection-state",
    "connection_nat_state": "connection-nat-state",
    "log_prefix": "log-prefix",
    "place_before": "place-before",
}


def _get(
    operation: Operation,
    path: str,
    params: dict[str, Any] | None = None,
) -> RouterOSPlan:
    return RouterOSPlan(
        operation=operation.name,
        capability="supported",
        steps=(RouterOSPlanStep(operation.action, "GET", path, params=params),),
    )


def _write(
    operation: Operation,
    method: str,
    path: str,
    body: dict[str, Any],
) -> RouterOSPlan:
    return RouterOSPlan(
        operation=operation.name,
        capability="supported",
        steps=(RouterOSPlanStep(operation.action, method, path, body=body),),
    )


def _toggle_by_id_or_match(
    operation: Operation,
    path: str,
    disabled: bool,
) -> RouterOSPlan:
    resource_id = operation.params.get("id")
    if isinstance(resource_id, str) and resource_id:
        return _write(
            operation,
            "PATCH",
            f"{path}/{resource_id}",
            {"disabled": disabled},
        )

    filters = _filters(operation)
    name = operation.params.get("name")
    if isinstance(name, str):
        filters["name"] = name
    if not filters:
        return _unsupported(
            operation,
            f"{operation.action} requires id, name, or match params",
        )

    return RouterOSPlan(
        operation=operation.name,
        capability="supported_via_fallback",
        steps=(
            RouterOSPlanStep("lookup", "GET", path, params=filters),
            RouterOSPlanStep(
                operation.action,
                "PATCH",
                f"{path}/<resolved-id>",
                body={"disabled": disabled},
            ),
        ),
        warnings=("operation requires resolving a RouterOS internal id before patch",),
    )


def _filters(operation: Operation) -> dict[str, Any]:
    match = operation.params.get("match", {})
    if isinstance(match, dict):
        return _translate_keys(match, {**ROUTE_KEY_MAP, **FIREWALL_RULE_KEY_MAP})
    return {}


def _body_map(operation: Operation, *keys: str) -> dict[str, Any]:
    for key in keys:
        value = operation.params.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _translate_keys(
    values: dict[str, Any],
    translation: dict[str, str],
) -> dict[str, Any]:
    return {
        translation.get(key, key.replace("_", "-")): value
        for key, value in values.items()
    }


def _unsupported(operation: Operation, reason: str) -> RouterOSPlan:
    return RouterOSPlan(
        operation=operation.name,
        capability="unsupported",
        steps=(),
        warnings=(reason,),
    )


def _row_sequence(data: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(data, dict):
        return (data,)
    if isinstance(data, (list, tuple)):
        return tuple(row for row in data if isinstance(row, dict))
    return ()


def _operation_with_target(operation: Operation, target: str) -> Operation:
    return Operation(
        namespace=operation.namespace,
        resource_path=operation.resource_path,
        action=operation.action,
        params={**operation.params, "target": target},
        source=operation.source,
    )


def _composed_error(
    operation: Operation,
    result: OperationResult,
    message: str,
) -> OperationResult:
    source_error = result.error
    return OperationResult(
        ok=False,
        operation=operation.name,
        target=operation.target,
        capability="supported_via_composition",
        adapter=dict(ROUTEROS_ADAPTER),
        warnings=result.warnings,
        error=ResultError(
            source_error.code if source_error else "COLLECTION_FAILED",
            f"{message}: {source_error.message}" if source_error else message,
            retryable=source_error.retryable if source_error else False,
            detail=source_error.detail if source_error else None,
        ),
    )


def _neighbor_device(row: dict[str, Any]) -> DeviceRecord:
    identity = _string(row.get("identity"))
    address = _string(row.get("address4") or row.get("address"))
    mac = _string(row.get("mac_address") or row.get("mac-address"))
    software_id = _string(row.get("software_id") or row.get("software-id"))
    return DeviceRecord(
        name=identity,
        host=address,
        mac=mac,
        serial=software_id,
        vendor=_string(row.get("platform")),
        platform=_string(row.get("board")),
        source="routeros:/ip/neighbor",
        identifiers=_neighbor_identifiers(row),
        metadata=_metadata(row),
    )


def _neighbor_identifiers(row: dict[str, Any]) -> tuple[str, ...]:
    identifiers = []
    discovered_by = _string(row.get("discovered_by") or row.get("discovered-by"))
    identity = _string(row.get("identity"))
    software_id = _string(row.get("software_id") or row.get("software-id"))
    if discovered_by and identity:
        identifiers.append(f"routeros:{discovered_by}/identity/{identity}")
    if software_id:
        identifiers.append(f"routeros:software-id/{software_id}")
    return tuple(identifiers)


def _neighbor_interface(row: dict[str, Any]) -> str | None:
    interface_name = _string(row.get("interface_name") or row.get("interface-name"))
    if interface_name and "/" in interface_name:
        return interface_name.rsplit("/", 1)[-1].strip()

    interface = _string(row.get("interface"))
    if interface and "," in interface:
        return interface.split(",", 1)[0].strip()
    return interface


def _arp_device(row: dict[str, Any]) -> DeviceRecord:
    host = _string(row.get("address"))
    mac = _string(row.get("mac_address") or row.get("mac-address"))
    return DeviceRecord(
        host=host,
        mac=mac,
        source="routeros:/ip/arp",
        metadata=_metadata(row),
    )


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key).replace("-", "_").replace(".", ""): value
        for key, value in row.items()
        if value not in {"", None}
    }


def _string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "on"}:
            return True
        if normalized in {"false", "no", "n", "0", "off"}:
            return False
    return None


def _bridge_port_status_inactive(status: str | None) -> bool | None:
    if not status:
        return None
    normalized = status.strip().lower()
    if normalized in {"inactive", "disabled"}:
        return True
    if normalized in {"in-bridge", "forwarding", "learning"}:
        return False
    return None


def _bridge_port_status_running(status: str | None) -> bool | None:
    if not status:
        return None
    normalized = status.strip().lower()
    if normalized in {"in-bridge", "forwarding"}:
        return True
    if normalized in {"inactive", "disabled"}:
        return False
    return None


@dataclass(frozen=True)
class _LookupResult:
    resource_id: str | None = None
    error: ResultError | None = None


def _extract_single_id(data: Any) -> _LookupResult:
    if isinstance(data, list):
        if not data:
            return _LookupResult(
                error=ResultError("LOOKUP_NOT_FOUND", "lookup returned no records")
            )
        if len(data) > 1:
            return _LookupResult(
                error=ResultError(
                    "LOOKUP_NOT_UNIQUE",
                    "lookup returned more than one record",
                    detail=data,
                )
            )
        return _extract_single_id(data[0])

    resource_id = _resource_id(data)
    if resource_id:
        return _LookupResult(resource_id=resource_id)
    return _LookupResult(
        error=ResultError("LOOKUP_MISSING_ID", "lookup result did not include an id")
    )


def _resource_id(data: Any) -> str | None:
    if isinstance(data, dict):
        value = data.get("id") or data.get(".id")
        return value if isinstance(value, str) and value else None
    value = getattr(data, "id", None)
    return value if isinstance(value, str) and value else None


def _result_error(
    operation: Operation,
    capability: str,
    code: str,
    message: str,
    warnings: tuple[str, ...] = (),
    detail: Any = None,
) -> OperationResult:
    return OperationResult(
        ok=False,
        operation=operation.name,
        target=operation.target,
        capability=capability,
        adapter=dict(ROUTEROS_ADAPTER),
        warnings=warnings,
        error=ResultError(code, message, detail=detail),
    )


def _clean_routeros_data(data: Any) -> Any:
    if isinstance(data, list):
        return [_clean_routeros_data(value) for value in data]
    if isinstance(data, dict):
        return {
            key.replace("-", "_").replace(".", ""): _clean_routeros_data(value)
            for key, value in data.items()
        }
    return data
