from __future__ import annotations
import os
from dataclasses import asdict
from pprint import pprint
from network_lang import target_device
from network_lang.adapters import plan_routeros_operation

apply_changes = os.environ.get("NETWORK_LANG_APPLY", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "on",
}

bridge = os.environ.get("NETWORK_LANG_EXAMPLE_BRIDGE", "bridge2")
bridge_port = os.environ.get("NETWORK_LANG_EXAMPLE_PORT", "ether8")
vlan_name = os.environ.get("NETWORK_LANG_EXAMPLE_VLAN", "vlan_mock_client")
vlan_id = int(os.environ.get("NETWORK_LANG_EXAMPLE_VLAN_ID", "220"))
updated_vlan_id = int(os.environ.get("NETWORK_LANG_EXAMPLE_UPDATED_VLAN_ID", "221"))

# ==================================================================
# Determine the target device to run the example operations on.
target = os.environ.get("NETWORK_LANG_TARGET", "edge-01")
device = target_device(target)

# ==================================================================
# Print the target device and whether the example operations will be executed or just planned.
print(f"target: {device.name} ({device.url})")
print(f"write operations: {'execute' if apply_changes else 'dry-run'}")

#==================================================================
# 1. List all neighbours of a device in the inventory.
print("\n=== 1. list all neighbours ===")
operation = device.operation("network.neighbors.list")
print(operation.name)
pprint(operation.params, sort_dicts=False)
result = device.execute(operation)
pprint(result.to_dict(), sort_dicts=False)

# ==================================================================
# 2. Create a dummy filter firewall rule of a device in the inventory.
print("\n=== 2. create a dummy disabled firewall filter rule ===")
operation = device.operation(
    "network.firewall.rules.create",
    rule={
        "chain": "forward",
        "action": "accept",
        "disabled": True,
        "comment": "network_lang mock_client disabled example rule",
    },
)

print(operation.name)
pprint(operation.params, sort_dicts=False)
if apply_changes:
    result = device.execute(operation)
    pprint(result.to_dict(), sort_dicts=False)
else:
    plan = plan_routeros_operation(operation)
    pprint(
        {
            "capability": plan.capability,
            "warnings": plan.warnings,
            "steps": [asdict(step) for step in plan.steps],
        },
        sort_dicts=False,
    )

# ==================================================================
# 3. List all firewall filters of a device in the inventory.
print("\n=== 3. list all firewall filters ===")
operation = device.operation("network.firewall.rules.list")
print(operation.name)
pprint(operation.params, sort_dicts=False)
result = device.execute(operation)
pprint(result.to_dict(), sort_dicts=False)

# ==================================================================
# 4. List all dynamically active connected routes of a device in the inventory.
print("\n=== 4. list dynamically active connected routes ===")
operation = device.operation(
    "network.routes.list",
    match={
        "dynamic": "true",
        "active": "true",
        "connect": "true",
    },
)

print(operation.name)
pprint(operation.params, sort_dicts=False)
result = device.execute(operation)
pprint(result.to_dict(), sort_dicts=False)

# ==================================================================
# 5. List all running slave interfaces of a device in the inventory.
print("\n=== 5. list running slave interfaces ===")
operation = device.operation(
    "network.interfaces.list",
    match={
        "running": "true",
        "slave": "true",
    },
)

print(operation.name)
pprint(operation.params, sort_dicts=False)
result = device.execute(operation)
pprint(result.to_dict(), sort_dicts=False)

# ==================================================================
# 6. Add a new port to bridge2 on a device in the inventory.
print(f"\n=== 6. add {bridge_port} to {bridge} ===")
operation = device.operation(
    "network.bridge.ports.create",
    port={
        "bridge": bridge,
        "interface": bridge_port,
        "comment": "network_lang mock_client bridge port example",
    },
)

print(operation.name)
pprint(operation.params, sort_dicts=False)
if apply_changes:
    result = device.execute(operation)
    pprint(result.to_dict(), sort_dicts=False)
else:
    plan = plan_routeros_operation(operation)
    pprint(
        {
            "capability": plan.capability,
            "warnings": plan.warnings,
            "steps": [asdict(step) for step in plan.steps],
        },
        sort_dicts=False,
    )

# ==================================================================
# 7. Create a new VLAN interface and attach it to bridge2.
print(f"\n=== 7. create {vlan_name} and attach it to {bridge} ===")
operation = device.operation(
    "network.vlans.create",
    vlan={
        "name": vlan_name,
        "interface": bridge,
        "vlan_id": vlan_id,
        "comment": "network_lang mock_client vlan example",
    },
)

print(operation.name)
pprint(operation.params, sort_dicts=False)
if apply_changes:
    result = device.execute(operation)
    pprint(result.to_dict(), sort_dicts=False)
else:
    plan = plan_routeros_operation(operation)
    pprint(
        {
            "capability": plan.capability,
            "warnings": plan.warnings,
            "steps": [asdict(step) for step in plan.steps],
        },
        sort_dicts=False,
    )

# ==================================================================
# 8. Edit/update the vlan-id of the previously created VLAN.
print(f"\n=== 8. update {vlan_name} vlan-id to {updated_vlan_id} ===")
operation = device.operation(
    "network.vlans.update",
    name=vlan_name,
    vlan={
        "vlan_id": updated_vlan_id,
        "comment": "network_lang mock_client vlan update example",
    },
)

print(operation.name)
pprint(operation.params, sort_dicts=False)
if apply_changes:
    result = device.execute(operation)
    pprint(result.to_dict(), sort_dicts=False)
else:
    plan = plan_routeros_operation(operation)
    pprint(
        {
            "capability": plan.capability,
            "warnings": plan.warnings,
            "steps": [asdict(step) for step in plan.steps],
        },
        sort_dicts=False,
    )
