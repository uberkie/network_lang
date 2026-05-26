"""Adapter planning helpers for network_lang."""

from .mikrotik_routeros import (
    RouterOSPlan,
    RouterOSPlanStep,
    RouterOSExecutor,
    RouterOSRestTransport,
    RouterOSTopologySnapshot,
    RouterOSTransport,
    collect_routeros_topology,
    execute_routeros_operation,
    plan_routeros_operation,
    preflight_routeros_operation,
    routeros_arp_to_attachments,
    routeros_arp_to_devices,
    routeros_bridge_hosts_to_attachments,
    routeros_bridge_ports_to_interface_states,
    routeros_neighbors_to_attachments,
    routeros_neighbors_to_devices,
)
from .ubnt_airos import (
    AirOSEndpoints,
    AirOSPlan,
    AirOSPlanStep,
    plan_airos_operation,
)

__all__ = [
    "AirOSEndpoints",
    "AirOSPlan",
    "AirOSPlanStep",
    "RouterOSPlan",
    "RouterOSPlanStep",
    "RouterOSExecutor",
    "RouterOSRestTransport",
    "RouterOSTopologySnapshot",
    "RouterOSTransport",
    "collect_routeros_topology",
    "execute_routeros_operation",
    "plan_airos_operation",
    "plan_routeros_operation",
    "preflight_routeros_operation",
    "routeros_arp_to_attachments",
    "routeros_arp_to_devices",
    "routeros_bridge_hosts_to_attachments",
    "routeros_bridge_ports_to_interface_states",
    "routeros_neighbors_to_attachments",
    "routeros_neighbors_to_devices",
]
