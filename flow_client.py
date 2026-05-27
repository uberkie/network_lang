from __future__ import annotations

import ipaddress
from pathlib import Path

from network_lang import (
    DeviceRecord,
    apply_flow_recon_policy,
    load_flow_devices,
    load_inventory,
    reconcile_devices,
)

CLIENT_GROUPS = {
    "client",
    "clients",
    "customer",
    "customers",
    "cpe",
    "cpe-devices",
}


def inventory_device(record):
    return DeviceRecord(
        name=record.get("name"),
        host=inventory_host(record),
        source="inventory",
        identifiers=tuple(
            f"inventory:{key}/{record[key]}" for key in ("id", "name") if record.get(key)
        ),
        metadata={"groups": record.get("groups", [])},
    )


def inventory_host(record):
    if record.get("host"):
        return str(record["host"])
    for interface in record.get("interfaces", []):
        value = (
            interface.get("ip_address")
            or interface.get("address")
            or interface.get("ip")
        )
        if value:
            return host_address(value)
    return None


def host_address(value):
    try:
        return str(ipaddress.ip_interface(str(value).strip()).ip)
    except ValueError:
        return str(value).split("/", 1)[0].strip()


def is_client(record):
    groups = {str(group).strip().lower() for group in record.get("groups", [])}
    return bool(groups & CLIENT_GROUPS)


flow_path = Path("flows.jsonl")
if not flow_path.exists() or flow_path.stat().st_size == 0:
    raise SystemExit("run flowcollector with -output flows.jsonl until it captures flows")

inventory = load_inventory()
expected = [inventory_device(record) for record in inventory if is_client(record)]
if not expected:
    raise SystemExit("no client records found in inventory")

infrastructure_hosts = [
    host
    for record in inventory
    if not is_client(record)
    for host in [inventory_host(record)]
    if host
]
observed = load_flow_devices(
    flow_path,
    scope="all",
    customer_hosts=[device.host for device in expected if device.host],
    known_infrastructure=infrastructure_hosts,
)
report = apply_flow_recon_policy(reconcile_devices(expected, observed))
print(report.to_text())
raise SystemExit(report.exit_code)
