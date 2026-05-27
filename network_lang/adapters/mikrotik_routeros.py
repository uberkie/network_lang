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
    """Collect read-only RouterOS topology observations into a single snapshot.

    Args:
        executor:
        target:
        network_device:
    """

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
    """Collect RouterOS topology and preflight an operation against it.

    Args:
        executor:
        operation:
        expected:
        network_device:
    """

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
    """

    Args:
        rows:

    Returns:

    """
    return tuple(_neighbor_device(row) for row in rows)


def routeros_neighbors_to_attachments(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    network_device: str,
) -> tuple[AttachmentRecord, ...]:
    """

    Args:
        rows:
        network_device:

    Returns:

    """
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
    """

    Args:
        rows:

    Returns:

    """
    return tuple(_arp_device(row) for row in rows)


def routeros_arp_to_attachments(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    network_device: str,
) -> tuple[AttachmentRecord, ...]:
    """

    Args:
        rows:
        network_device:

    Returns:

    """
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
    """

    Args:
        rows:
        network_device:

    Returns:

    """
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
    """

    Args:
        rows:
        network_device:

    Returns:

    """
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
    """Translate a vendor-neutral operation into RouterOS REST API calls.

    Args:
        operation:
    """

    if operation.name == "network.system.identity.get":
        return _get(operation, "/system/identity")

    ppp_command = _ppp_command_path(operation)
    if ppp_command:
        return _run(operation, ppp_command, _command_body(operation))

    ppp_endpoint = _ppp_endpoint_path(operation)
    if ppp_endpoint:
        return _plan_ppp_endpoint(operation, ppp_endpoint)

    radius_command = _radius_command_path(operation)
    if radius_command:
        return _run(operation, radius_command, _command_body(operation))

    radius_endpoint = _radius_endpoint_path(operation)
    if radius_endpoint:
        return _plan_radius_endpoint(operation, radius_endpoint)

    routing_command = _routing_command_path(operation)
    if routing_command:
        return _run(operation, routing_command, _command_body(operation))

    routing_endpoint = _routing_endpoint_path(operation)
    if routing_endpoint:
        return _plan_routing_endpoint(operation, routing_endpoint)

    ip_endpoint = _ip_endpoint_path(operation)
    if ip_endpoint:
        return _plan_ip_endpoint(operation, ip_endpoint)

    ip_command = _ip_command_path(operation)
    if ip_command:
        return _run(operation, ip_command, _command_body(operation))

    interface_endpoint = _interface_endpoint_path(operation)
    if interface_endpoint:
        return _plan_interface_endpoint(operation, interface_endpoint)

    interface_command = _interface_command_path(operation)
    if interface_command:
        return _run(operation, interface_command, _command_body(operation))

    if operation.name == "network.neighbors.list":
        return _get(operation, "/ip/neighbor", _filters(operation))

    if operation.name == "network.bridge.hosts.list":
        return _get(operation, "/interface/bridge/host", _filters(operation))

    if operation.name == "network.bridge.ports.list":
        return _get(operation, "/interface/bridge/port", _filters(operation))

    if operation.name == "network.bridge.ports.create":
        port = _body_map(operation, "port", "data")
        if not port:
            return _unsupported(operation, "bridge port create requires port or data params")
        return _write(
            operation,
            "PUT",
            "/interface/bridge/port",
            _translate_keys(port, BRIDGE_PORT_KEY_MAP),
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

    if operation.name == "network.vlans.create":
        vlan = _body_map(operation, "vlan", "data")
        if not vlan:
            return _unsupported(operation, "vlan create requires vlan or data params")
        return _write(
            operation,
            "PUT",
            "/interface/vlan",
            _translate_keys(vlan, VLAN_KEY_MAP),
        )

    if operation.name == "network.vlans.update":
        vlan = _body_map(operation, "vlan", "data")
        if not vlan:
            return _unsupported(operation, "vlan update requires vlan or data params")
        return _update_by_id_or_match(
            operation,
            "/interface/vlan",
            _translate_keys(vlan, VLAN_KEY_MAP),
        )

    if operation.name == "network.wireless.clients.list":
        return _get(
            operation,
            "/interface/wireless/registration-table",
            _filters(operation),
        )

    return _unsupported(operation, "operation is not mapped for RouterOS")


PPP_ENDPOINTS = {
    ("aaa",): "/ppp/aaa",
    ("active",): "/ppp/active",
    ("l2tp_secret",): "/ppp/l2tp-secret",
    ("profile",): "/ppp/profile",
    ("secret",): "/ppp/secret",
}

PPP_COMMANDS = {
    ("export",): "/ppp/export",
}


def _ppp_endpoint_path(operation: Operation) -> str | None:
    if operation.namespace != "network":
        return None
    if not operation.resource_path or operation.resource_path[0] != "ppp":
        return None
    return PPP_ENDPOINTS.get(operation.resource_path[1:])


def _ppp_command_path(operation: Operation) -> str | None:
    if operation.namespace != "network" or operation.action != "run":
        return None
    if not operation.resource_path or operation.resource_path[0] != "ppp":
        return None

    command = operation.resource_path[1:]
    if command in PPP_COMMANDS:
        return PPP_COMMANDS[command]
    if len(command) < 2:
        return None

    endpoint = PPP_ENDPOINTS.get(command[:-1])
    command_path = PPP_COMMANDS.get(command[-1:])
    if endpoint and command_path:
        return f"{endpoint}/{command_path.rsplit('/', 1)[-1]}"
    return None


def _plan_ppp_endpoint(operation: Operation, path: str) -> RouterOSPlan:
    if operation.action == "list":
        return _get(operation, path, _filters(operation))
    if operation.action == "get":
        return _get_by_id_or_match(operation, path)
    if operation.action == "create":
        body = _ppp_body(operation)
        if not body:
            return _unsupported(operation, "ppp endpoint create requires data params")
        return _write(operation, "PUT", path, body)
    if operation.action == "update":
        body = _ppp_body(operation)
        if not body:
            return _unsupported(operation, "ppp endpoint update requires data params")
        return _update_by_id_or_match(operation, path, body)
    if operation.action == "delete":
        return _delete_by_id_or_match(operation, path)
    if operation.action in {"enable", "disable"}:
        return _toggle_by_id_or_match(
            operation,
            path,
            disabled=operation.action == "disable",
        )
    return _unsupported(
        operation,
        f"ppp endpoint does not support action {operation.action!r}",
    )


RADIUS_ENDPOINTS = {
    (): "/radius",
    ("incoming",): "/radius/incoming",
}

RADIUS_COMMANDS = {
    ("add",): "/radius/add",
    ("comment",): "/radius/comment",
    ("disable",): "/radius/disable",
    ("edit",): "/radius/edit",
    ("enable",): "/radius/enable",
    ("export",): "/radius/export",
    ("find",): "/radius/find",
    ("monitor",): "/radius/monitor",
    ("move",): "/radius/move",
    ("print",): "/radius/print",
    ("remove",): "/radius/remove",
    ("reset",): "/radius/reset",
    ("reset_counters",): "/radius/reset-counters",
    ("set",): "/radius/set",
}


def _radius_endpoint_path(operation: Operation) -> str | None:
    if operation.namespace != "network":
        return None
    if not operation.resource_path or operation.resource_path[0] != "radius":
        return None
    return RADIUS_ENDPOINTS.get(operation.resource_path[1:])


def _radius_command_path(operation: Operation) -> str | None:
    if operation.namespace != "network" or operation.action != "run":
        return None
    if not operation.resource_path or operation.resource_path[0] != "radius":
        return None

    command = operation.resource_path[1:]
    if command in RADIUS_COMMANDS:
        return RADIUS_COMMANDS[command]
    if len(command) < 2:
        return None

    endpoint = RADIUS_ENDPOINTS.get(command[:-1])
    command_path = RADIUS_COMMANDS.get(command[-1:])
    if endpoint and command_path:
        return f"{endpoint}/{command_path.rsplit('/', 1)[-1]}"
    return None


def _plan_radius_endpoint(operation: Operation, path: str) -> RouterOSPlan:
    if operation.action == "list":
        return _get(operation, path, _filters(operation))
    if operation.action == "get":
        return _get_by_id_or_match(operation, path)
    if operation.action == "create":
        body = _radius_body(operation)
        if not body:
            return _unsupported(operation, "radius endpoint create requires data params")
        return _write(operation, "PUT", path, body)
    if operation.action == "update":
        body = _radius_body(operation)
        if not body:
            return _unsupported(operation, "radius endpoint update requires data params")
        return _update_by_id_or_match(operation, path, body)
    if operation.action == "delete":
        return _delete_by_id_or_match(operation, path)
    if operation.action in {"enable", "disable"}:
        return _toggle_by_id_or_match(
            operation,
            path,
            disabled=operation.action == "disable",
        )
    return _unsupported(
        operation,
        f"radius endpoint does not support action {operation.action!r}",
    )


ROUTING_ENDPOINTS = {
    ("bfd",): "/routing/bfd",
    ("bgp",): "/routing/bgp",
    ("fantasy",): "/routing/fantasy",
    ("filter",): "/routing/filter",
    ("gmp",): "/routing/gmp",
    ("id",): "/routing/id",
    ("igmp_proxy",): "/routing/igmp-proxy",
    ("isis",): "/routing/isis",
    ("nexthop",): "/routing/nexthop",
    ("ospf",): "/routing/ospf",
    ("pimsm",): "/routing/pimsm",
    ("rip",): "/routing/rip",
    ("route",): "/routing/route",
    ("rpki",): "/routing/rpki",
    ("rule",): "/routing/rule",
    ("settings",): "/routing/settings",
    ("stats",): "/routing/stats",
    ("table",): "/routing/table",
}

ROUTING_COMMANDS = {
    ("discourse",): "/routing/discourse",
    ("export",): "/routing/export",
    ("reinstall_fib",): "/routing/reinstall-fib",
}


def _routing_endpoint_path(operation: Operation) -> str | None:
    if operation.namespace != "network":
        return None
    if not operation.resource_path or operation.resource_path[0] != "routing":
        return None
    return ROUTING_ENDPOINTS.get(operation.resource_path[1:])


def _routing_command_path(operation: Operation) -> str | None:
    if operation.namespace != "network" or operation.action != "run":
        return None
    if not operation.resource_path or operation.resource_path[0] != "routing":
        return None
    return ROUTING_COMMANDS.get(operation.resource_path[1:])


def _plan_routing_endpoint(operation: Operation, path: str) -> RouterOSPlan:
    if operation.action == "list":
        return _get(operation, path, _filters(operation))
    if operation.action == "get":
        return _get_by_id_or_match(operation, path)
    if operation.action == "create":
        body = _routing_body(operation)
        if not body:
            return _unsupported(operation, "routing endpoint create requires data params")
        return _write(operation, "PUT", path, body)
    if operation.action == "update":
        body = _routing_body(operation)
        if not body:
            return _unsupported(operation, "routing endpoint update requires data params")
        return _update_by_id_or_match(operation, path, body)
    if operation.action == "delete":
        return _delete_by_id_or_match(operation, path)
    if operation.action in {"enable", "disable"}:
        return _toggle_by_id_or_match(
            operation,
            path,
            disabled=operation.action == "disable",
        )
    return _unsupported(
        operation,
        f"routing endpoint does not support action {operation.action!r}",
    )


IP_ENDPOINTS = {
    ("address",): "/ip/address",
    ("arp",): "/ip/arp",
    ("cloud",): "/ip/cloud",
    ("dhcp_client",): "/ip/dhcp-client",
    ("dhcp_relay",): "/ip/dhcp-relay",
    ("dhcp_server",): "/ip/dhcp-server",
    ("dns",): "/ip/dns",
    ("firewall",): "/ip/firewall",
    ("hotspot",): "/ip/hotspot",
    ("ipsec",): "/ip/ipsec",
    ("kid_control",): "/ip/kid-control",
    ("media",): "/ip/media",
    ("nat_pmp",): "/ip/nat-pmp",
    ("neighbor",): "/ip/neighbor",
    ("packing",): "/ip/packing",
    ("pool",): "/ip/pool",
    ("proxy",): "/ip/proxy",
    ("route",): "/ip/route",
    ("service",): "/ip/service",
    ("settings",): "/ip/settings",
    ("smb",): "/ip/smb",
    ("socks",): "/ip/socks",
    ("ssh",): "/ip/ssh",
    ("tftp",): "/ip/tftp",
    ("traffic_flow",): "/ip/traffic-flow",
    ("upnp",): "/ip/upnp",
    ("vrf",): "/ip/vrf",
}

IP_COMMANDS = {
    ("export",): "/ip/export",
}


def _ip_endpoint_path(operation: Operation) -> str | None:
    if operation.namespace != "network":
        return None
    if not operation.resource_path or operation.resource_path[0] != "ip":
        return None
    return IP_ENDPOINTS.get(operation.resource_path[1:])


def _ip_command_path(operation: Operation) -> str | None:
    if operation.namespace != "network" or operation.action != "run":
        return None
    if not operation.resource_path or operation.resource_path[0] != "ip":
        return None
    return IP_COMMANDS.get(operation.resource_path[1:])


def _plan_ip_endpoint(operation: Operation, path: str) -> RouterOSPlan:
    if operation.action == "list":
        return _get(operation, path, _filters(operation))
    if operation.action == "get":
        return _get_by_id_or_match(operation, path)
    if operation.action == "create":
        body = _ip_body(operation)
        if not body:
            return _unsupported(operation, "ip endpoint create requires data params")
        return _write(operation, "PUT", path, body)
    if operation.action == "update":
        body = _ip_body(operation)
        if not body:
            return _unsupported(operation, "ip endpoint update requires data params")
        return _update_by_id_or_match(operation, path, body)
    if operation.action == "delete":
        return _delete_by_id_or_match(operation, path)
    if operation.action in {"enable", "disable"}:
        return _toggle_by_id_or_match(
            operation,
            path,
            disabled=operation.action == "disable",
        )
    return _unsupported(
        operation,
        f"ip endpoint does not support action {operation.action!r}",
    )


INTERFACE_ENDPOINTS = {
    (): "/interface",
    ("six_to_four",): "/interface/6to4",
    ("bonding",): "/interface/bonding",
    ("bridge",): "/interface/bridge",
    ("bridge", "hosts"): "/interface/bridge/host",
    ("bridge", "ports"): "/interface/bridge/port",
    ("detect_internet",): "/interface/detect-internet",
    ("dot1x",): "/interface/dot1x",
    ("eoip",): "/interface/eoip",
    ("eoipv6",): "/interface/eoipv6",
    ("ethernet",): "/interface/ethernet",
    ("gre",): "/interface/gre",
    ("gre6",): "/interface/gre6",
    ("ipip",): "/interface/ipip",
    ("ipipv6",): "/interface/ipipv6",
    ("l2tp_client",): "/interface/l2tp-client",
    ("l2tp_ether",): "/interface/l2tp-ether",
    ("l2tp_server",): "/interface/l2tp-server",
    ("lists",): "/interface/list",
    ("interface_lists",): "/interface/list",
    ("lte",): "/interface/lte",
    ("macsec",): "/interface/macsec",
    ("macvlan",): "/interface/macvlan",
    ("mesh",): "/interface/mesh",
    ("ovpn_client",): "/interface/ovpn-client",
    ("ovpn_server",): "/interface/ovpn-server",
    ("ppp_client",): "/interface/ppp-client",
    ("ppp_server",): "/interface/ppp-server",
    ("pppoe_client",): "/interface/pppoe-client",
    ("pppoe_server",): "/interface/pppoe-server",
    ("pptp_client",): "/interface/pptp-client",
    ("pptp_server",): "/interface/pptp-server",
    ("sstp_client",): "/interface/sstp-client",
    ("sstp_server",): "/interface/sstp-server",
    ("veth",): "/interface/veth",
    ("vlan",): "/interface/vlan",
    ("vpls",): "/interface/vpls",
    ("vrrp",): "/interface/vrrp",
    ("vxlan",): "/interface/vxlan",
    ("wifi",): "/interface/wifi",
    ("wireguard",): "/interface/wireguard",
    ("wireless",): "/interface/wireless",
    ("wireless", "registration_table"): "/interface/wireless/registration-table",
}

INTERFACE_COMMANDS = {
    ("blink",): "/interface/blink",
    ("comment",): "/interface/comment",
    ("edit",): "/interface/edit",
    ("export",): "/interface/export",
    ("find",): "/interface/find",
    ("monitor_traffic",): "/interface/monitor-traffic",
    ("print",): "/interface/print",
    ("reset",): "/interface/reset",
    ("reset_counters",): "/interface/reset-counters",
    ("set",): "/interface/set",
}


def _interface_endpoint_path(operation: Operation) -> str | None:
    if operation.namespace != "network":
        return None
    if not operation.resource_path or operation.resource_path[0] != "interfaces":
        return None
    return INTERFACE_ENDPOINTS.get(operation.resource_path[1:])


def _interface_command_path(operation: Operation) -> str | None:
    if operation.namespace != "network" or operation.action != "run":
        return None
    if not operation.resource_path or operation.resource_path[0] != "interfaces":
        return None

    command = operation.resource_path[1:]
    if command in INTERFACE_COMMANDS:
        return INTERFACE_COMMANDS[command]
    if len(command) < 2:
        return None

    endpoint = INTERFACE_ENDPOINTS.get(command[:-1])
    command_name = command[-1:]
    command_path = INTERFACE_COMMANDS.get(command_name)
    if endpoint and command_path:
        return f"{endpoint}/{command_path.rsplit('/', 1)[-1]}"
    return None


def _plan_interface_endpoint(operation: Operation, path: str) -> RouterOSPlan:
    if operation.action == "list":
        return _get(operation, path, _filters(operation))
    if operation.action == "get":
        return _get_by_id_or_match(operation, path)
    if operation.action == "create":
        body = _interface_body(operation)
        if not body:
            return _unsupported(operation, "interface create requires data params")
        return _write(operation, "PUT", path, body)
    if operation.action == "update":
        body = _interface_body(operation)
        if not body:
            return _unsupported(operation, "interface update requires data params")
        return _update_by_id_or_match(operation, path, body)
    if operation.action == "delete":
        return _delete_by_id_or_match(operation, path)
    if operation.action in {"enable", "disable"}:
        return _toggle_by_id_or_match(
            operation,
            path,
            disabled=operation.action == "disable",
        )
    return _unsupported(
        operation,
        f"interface endpoint does not support action {operation.action!r}",
    )


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

BRIDGE_PORT_KEY_MAP = {
    "auto_isolate": "auto-isolate",
    "bpdu_guard": "bpdu-guard",
    "broadcast_flood": "broadcast-flood",
    "fast_leave": "fast-leave",
    "frame_types": "frame-types",
    "ingress_filtering": "ingress-filtering",
    "internal_path_cost": "internal-path-cost",
    "path_cost": "path-cost",
    "point_to_point": "point-to-point",
    "restricted_role": "restricted-role",
    "restricted_tcn": "restricted-tcn",
    "tag_stacking": "tag-stacking",
    "unknown_multicast_flood": "unknown-multicast-flood",
    "unknown_unicast_flood": "unknown-unicast-flood",
}

VLAN_KEY_MAP = {
    "vlan_id": "vlan-id",
    "use_service_tag": "use-service-tag",
    "arp": "arp",
    "local_proxy_arp": "local-proxy-arp",
    "proxy_arp": "proxy-arp",
    "reply_only": "reply-only",
}

IP_KEY_MAP = {
    **ROUTE_KEY_MAP,
    **FIREWALL_RULE_KEY_MAP,
    "add_default_route": "add-default-route",
    "address": "address",
    "allow_remote_requests": "allow-remote-requests",
    "cache_max_ttl": "cache-max-ttl",
    "cache_size": "cache-size",
    "dhcp_options": "dhcp-options",
    "disabled": "disabled",
    "dns_servers": "dns-servers",
    "gateway": "gateway",
    "interface": "interface",
    "lease_time": "lease-time",
    "local_address": "local-address",
    "mac_address": "mac-address",
    "max_udp_packet_size": "max-udp-packet-size",
    "name": "name",
    "query_server_timeout": "query-server-timeout",
    "query_total_timeout": "query-total-timeout",
    "remote_address": "remote-address",
    "server_address": "server-address",
    "use_peer_dns": "use-peer-dns",
    "use_peer_ntp": "use-peer-ntp",
}

ROUTING_KEY_MAP = {
    **ROUTE_KEY_MAP,
    "address_families": "address-families",
    "as": "as",
    "bgp_as_path": "bgp-as-path",
    "chain": "chain",
    "check_gateway": "check-gateway",
    "comment": "comment",
    "disabled": "disabled",
    "distance": "distance",
    "dst": "dst-address",
    "dst_address": "dst-address",
    "gateway": "gateway",
    "in_filter": "in-filter",
    "instance": "instance",
    "local_address": "local-address",
    "name": "name",
    "out_filter": "out-filter",
    "pref_src": "pref-src",
    "remote_address": "remote-address",
    "routing_table": "routing-table",
    "router_id": "router-id",
    "scope": "scope",
    "suppress_hw_offload": "suppress-hw-offload",
    "table": "routing-table",
    "target_scope": "target-scope",
    "template": "template",
    "vrf_interface": "vrf-interface",
}

RADIUS_KEY_MAP = {
    "accounting_backup": "accounting-backup",
    "accounting_port": "accounting-port",
    "address": "address",
    "authentication_port": "authentication-port",
    "called_id": "called-id",
    "certificate": "certificate",
    "comment": "comment",
    "disabled": "disabled",
    "domain": "domain",
    "protocol": "protocol",
    "realm": "realm",
    "secret": "secret",
    "service": "service",
    "src": "src-address",
    "src_address": "src-address",
    "timeout": "timeout",
    "vrf": "vrf",
}

PPP_KEY_MAP = {
    "address_list": "address-list",
    "allow": "allow",
    "change_tcp_mss": "change-tcp-mss",
    "comment": "comment",
    "copy_from": "copy-from",
    "default_profile": "default-profile",
    "disabled": "disabled",
    "dns_server": "dns-server",
    "encoding": "encoding",
    "idle_timeout": "idle-timeout",
    "incoming_filter": "incoming-filter",
    "insert_queue_before": "insert-queue-before",
    "interface": "interface",
    "keepalive_timeout": "keepalive-timeout",
    "limits_bytes_in": "limits-bytes-in",
    "limits_bytes_out": "limits-bytes-out",
    "local_address": "local-address",
    "name": "name",
    "only_one": "only-one",
    "outgoing_filter": "outgoing-filter",
    "parent_queue": "parent-queue",
    "password": "password",
    "profile": "profile",
    "rate_limit": "rate-limit",
    "remote_address": "remote-address",
    "remote_ipv6_prefix_pool": "remote-ipv6-prefix-pool",
    "routes": "routes",
    "secret": "secret",
    "service": "service",
    "session_timeout": "session-timeout",
    "use_compression": "use-compression",
    "use_encryption": "use-encryption",
    "use_ipv6": "use-ipv6",
    "use_mpls": "use-mpls",
    "use_upnp": "use-upnp",
    "wins_server": "wins-server",
}

INTERFACE_KEY_MAP = {
    **BRIDGE_PORT_KEY_MAP,
    **VLAN_KEY_MAP,
    "actual_mtu": "actual-mtu",
    "allow_fast_path": "allow-fast-path",
    "arp_timeout": "arp-timeout",
    "auto_negotiation": "auto-negotiation",
    "bridge": "bridge",
    "comment": "comment",
    "default_name": "default-name",
    "disabled": "disabled",
    "interface": "interface",
    "keepalive_timeout": "keepalive-timeout",
    "l2mtu": "l2mtu",
    "mac_address": "mac-address",
    "master_port": "master-port",
    "max_l2mtu": "max-l2mtu",
    "mtu": "mtu",
    "name": "name",
    "running": "running",
    "rx_byte": "rx-byte",
    "rx_packet": "rx-packet",
    "tx_byte": "tx-byte",
    "tx_packet": "tx-packet",
    "vlan_id": "vlan-id",
}

ROUTEROS_GRAPH_RATE_FIELDS = {
    "rx_mbps": "rx_byte",
    "tx_mbps": "tx_byte",
}

ROUTEROS_GRAPH_COUNTER_FIELDS = {
    "rx_byte": "rx_mbps",
    "tx_byte": "tx_mbps",
}

FILTER_KEY_MAP = {
    **ROUTE_KEY_MAP,
    **FIREWALL_RULE_KEY_MAP,
    **IP_KEY_MAP,
    **ROUTING_KEY_MAP,
    **RADIUS_KEY_MAP,
    **PPP_KEY_MAP,
    **INTERFACE_KEY_MAP,
}


def routeros_default_graph_group_by(operation_name: str) -> str | None:
    if operation_name.startswith("network.interfaces"):
        return "interface"
    return None


def routeros_prepare_graph_records(
    records: Iterable[dict[str, Any]],
    *,
    y: Any,
    x: str = "timestamp",
    group_by: Any = None,
    samples: int = 1,
    kind: str = "line",
    rate: bool | None = None,
) -> tuple[tuple[dict[str, Any], ...], Any]:
    metrics = _graph_fields(y)
    output_metrics: list[Any] = []
    counters: list[str] = []

    for metric in metrics:
        if not isinstance(metric, str):
            output_metrics.append(metric)
            continue

        normalized = metric.replace("-", "_")
        counter = ROUTEROS_GRAPH_RATE_FIELDS.get(normalized)
        if counter:
            counters.append(counter)
            output_metrics.append(normalized)
            continue

        output = ROUTEROS_GRAPH_COUNTER_FIELDS.get(normalized)
        if kind == "line" and samples > 1 and output and rate is not False:
            counters.append(normalized)
            output_metrics.append(output)
            continue

        output_metrics.append(metric)

    if counters:
        if samples < 2:
            raise ValueError("rate graph metrics need at least 2 samples")
        from ..graphing import counter_rate_records

        records = counter_rate_records(
            records,
            counters=tuple(dict.fromkeys(counters)),
            group_by=group_by,
            x=x,
            scale=0.000008,
            suffix="_mbps",
        )
    else:
        records = tuple(records)

    return records, _graph_field_value(output_metrics)


def _graph_fields(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        fields = tuple(part.strip() for part in value.split(",") if part.strip())
        return fields or (value,)
    try:
        return tuple(value)
    except TypeError:
        return (value,)


def _graph_field_value(fields: list[Any]) -> Any:
    if len(fields) == 1:
        return fields[0]
    return tuple(fields)


def _get(
    operation: Operation,
    path: str,
    params: dict[str, Any] | None = None,
) -> RouterOSPlan:
    """

    Args:
        operation:
        path:
        params:

    Returns:

    """
    return RouterOSPlan(
        operation=operation.name,
        capability="supported",
        steps=(RouterOSPlanStep(operation.action, "GET", path, params=params),),
    )


def _get_by_id_or_match(operation: Operation, path: str) -> RouterOSPlan:
    resource_id = operation.params.get("id")
    if isinstance(resource_id, str) and resource_id:
        return _get(operation, f"{path}/{resource_id}")

    filters = _resource_filters(operation)
    if not filters:
        return _unsupported(operation, "get requires id, name, or match params")
    return _get(operation, path, filters)


def _write(
    operation: Operation,
    method: str,
    path: str,
    body: dict[str, Any],
) -> RouterOSPlan:
    """

    Args:
        operation:
        method:
        path:
        body:

    Returns:

    """
    return RouterOSPlan(
        operation=operation.name,
        capability="supported",
        steps=(RouterOSPlanStep(operation.action, method, path, body=body),),
    )


def _run(
    operation: Operation,
    path: str,
    body: dict[str, Any],
) -> RouterOSPlan:
    return RouterOSPlan(
        operation=operation.name,
        capability="supported",
        steps=(RouterOSPlanStep(operation.action, "POST", path, body=body),),
    )


def _toggle_by_id_or_match(
    operation: Operation,
    path: str,
    disabled: bool,
) -> RouterOSPlan:
    """

    Args:
        operation:
        path:
        disabled:

    Returns:

    """
    resource_id = operation.params.get("id")
    if isinstance(resource_id, str) and resource_id:
        return _write(
            operation,
            "PATCH",
            f"{path}/{resource_id}",
            {"disabled": disabled},
        )

    filters = _resource_filters(operation)
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


def _update_by_id_or_match(
    operation: Operation,
    path: str,
    body: dict[str, Any],
) -> RouterOSPlan:
    """

    Args:
        operation:
        path:
        body:

    Returns:

    """
    resource_id = operation.params.get("id")
    if isinstance(resource_id, str) and resource_id:
        return _write(operation, "PATCH", f"{path}/{resource_id}", body)

    filters = _resource_filters(operation)
    if not filters:
        return _unsupported(operation, "update requires id, name, or match params")

    return RouterOSPlan(
        operation=operation.name,
        capability="supported_via_fallback",
        steps=(
            RouterOSPlanStep("lookup", "GET", path, params=filters),
            RouterOSPlanStep(
                operation.action,
                "PATCH",
                f"{path}/<resolved-id>",
                body=body,
            ),
        ),
        warnings=("operation requires resolving a RouterOS internal id before patch",),
    )


def _delete_by_id_or_match(
    operation: Operation,
    path: str,
) -> RouterOSPlan:
    resource_id = operation.params.get("id")
    if isinstance(resource_id, str) and resource_id:
        return RouterOSPlan(
            operation=operation.name,
            capability="supported",
            steps=(RouterOSPlanStep(operation.action, "DELETE", f"{path}/{resource_id}"),),
        )

    filters = _resource_filters(operation)
    if not filters:
        return _unsupported(operation, "delete requires id, name, or match params")

    return RouterOSPlan(
        operation=operation.name,
        capability="supported_via_fallback",
        steps=(
            RouterOSPlanStep("lookup", "GET", path, params=filters),
            RouterOSPlanStep(operation.action, "DELETE", f"{path}/<resolved-id>"),
        ),
        warnings=("operation requires resolving a RouterOS internal id before delete",),
    )


def _filters(operation: Operation) -> dict[str, Any]:
    """

    Args:
        operation:

    Returns:

    """
    match = operation.params.get("match", {})
    if isinstance(match, dict):
        return _translate_keys(match, FILTER_KEY_MAP)
    return {}


def _resource_filters(operation: Operation) -> dict[str, Any]:
    filters = _filters(operation)
    name = operation.params.get("name")
    if isinstance(name, str) and name:
        filters["name"] = name
    return filters


def _body_map(operation: Operation, *keys: str) -> dict[str, Any]:
    """

    Args:
        operation:
        *keys:

    Returns:

    """
    for key in keys:
        value = operation.params.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _interface_body(operation: Operation) -> dict[str, Any]:
    body = _body_map(operation, "data", "interface")
    if not body and operation.resource_path:
        body = _body_map(operation, operation.resource_path[-1])
    return _translate_keys(body, INTERFACE_KEY_MAP)


def _ip_body(operation: Operation) -> dict[str, Any]:
    body = _body_map(operation, "data", "ip")
    if not body and operation.resource_path:
        body = _body_map(operation, operation.resource_path[-1])
    return _translate_keys(body, IP_KEY_MAP)


def _routing_body(operation: Operation) -> dict[str, Any]:
    body = _body_map(operation, "data", "routing")
    if not body and operation.resource_path:
        body = _body_map(operation, operation.resource_path[-1])
    return _translate_keys(body, ROUTING_KEY_MAP)


def _radius_body(operation: Operation) -> dict[str, Any]:
    body = _body_map(operation, "data", "radius")
    if not body and operation.resource_path:
        body = _body_map(operation, operation.resource_path[-1])
    return _translate_keys(body, RADIUS_KEY_MAP)


def _ppp_body(operation: Operation) -> dict[str, Any]:
    body = _body_map(operation, "data", "ppp")
    if not body and operation.resource_path:
        body = _body_map(operation, operation.resource_path[-1])
    return _translate_keys(body, PPP_KEY_MAP)


def _command_body(operation: Operation) -> dict[str, Any]:
    body = _body_map(operation, "data", "params", "command")
    direct = {
        key: value
        for key, value in operation.params.items()
        if key not in {"target", "data", "params", "command"}
    }
    return _translate_keys({**body, **direct}, INTERFACE_KEY_MAP)


def _translate_keys(
    values: dict[str, Any],
    translation: dict[str, str],
) -> dict[str, Any]:
    """

    Args:
        values:
        translation:

    Returns:

    """
    return {
        translation.get(key, key.replace("_", "-")): value
        for key, value in values.items()
    }


def _unsupported(operation: Operation, reason: str) -> RouterOSPlan:
    """

    Args:
        operation:
        reason:

    Returns:

    """
    return RouterOSPlan(
        operation=operation.name,
        capability="unsupported",
        steps=(),
        warnings=(reason,),
    )


def _row_sequence(data: Any) -> tuple[dict[str, Any], ...]:
    """

    Args:
        data:

    Returns:

    """
    if isinstance(data, dict):
        return (data,)
    if isinstance(data, (list, tuple)):
        return tuple(row for row in data if isinstance(row, dict))
    return ()


def _operation_with_target(operation: Operation, target: str) -> Operation:
    """

    Args:
        operation:
        target:

    Returns:

    """
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
    """

    Args:
        operation:
        result:
        message:

    Returns:

    """
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
    """

    Args:
        row:

    Returns:

    """
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
    """

    Args:
        row:

    Returns:

    """
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
    """

    Args:
        row:

    Returns:

    """
    interface_name = _string(row.get("interface_name") or row.get("interface-name"))
    if interface_name and "/" in interface_name:
        return interface_name.rsplit("/", 1)[-1].strip()

    interface = _string(row.get("interface"))
    if interface and "," in interface:
        return interface.split(",", 1)[0].strip()
    return interface


def _arp_device(row: dict[str, Any]) -> DeviceRecord:
    """

    Args:
        row:

    Returns:

    """
    host = _string(row.get("address"))
    mac = _string(row.get("mac_address") or row.get("mac-address"))
    return DeviceRecord(
        host=host,
        mac=mac,
        source="routeros:/ip/arp",
        metadata=_metadata(row),
    )


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    """

    Args:
        row:

    Returns:

    """
    return {
        str(key).replace("-", "_").replace(".", ""): value
        for key, value in row.items()
        if value not in {"", None}
    }


def _string(value: Any) -> str | None:
    """

    Args:
        value:

    Returns:

    """
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _bool(value: Any) -> bool | None:
    """

    Args:
        value:

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
    return None


def _bridge_port_status_inactive(status: str | None) -> bool | None:
    """

    Args:
        status:

    Returns:

    """
    if not status:
        return None
    normalized = status.strip().lower()
    if normalized in {"inactive", "disabled"}:
        return True
    if normalized in {"in-bridge", "forwarding", "learning"}:
        return False
    return None


def _bridge_port_status_running(status: str | None) -> bool | None:
    """

    Args:
        status:

    Returns:

    """
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
    """

    Args:
        data:

    Returns:

    """
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
    """

    Args:
        data:

    Returns:

    """
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
    """

    Args:
        operation:
        capability:
        code:
        message:
        warnings:
        detail:

    Returns:

    """
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
    """

    Args:
        data:

    Returns:

    """
    if isinstance(data, list):
        return [_clean_routeros_data(value) for value in data]
    if isinstance(data, dict):
        return {
            key.replace("-", "_").replace(".", ""): _clean_routeros_data(value)
            for key, value in data.items()
        }
    return data
