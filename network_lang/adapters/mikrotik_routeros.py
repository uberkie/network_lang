from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..model import Operation


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
