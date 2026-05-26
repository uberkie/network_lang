# Unified Network Syntax

This repository is a starting point for an abstracted network operation syntax:
a library-first, vendor-neutral intent layer that can map the same operator
action onto different device interfaces such as SSH, REST, NETCONF, RESTCONF,
SNMP, RouterOS API, vendor SDKs, and parser fallbacks.

The central idea is simple:

```text
operator intent
  -> unified operation tree
  -> capability resolver
  -> adapter selection
  -> device execution
  -> normalized result
```

The syntax should not pretend that every device supports the same behavior.
It should expose one stable operation model while being honest about device
capabilities, transport limits, permissions, and partial results.

The primary interface is the Python library. Text files and CLI commands are
optional ways to load, validate, and inspect the same operation model.

## Design Principles

1. Intent is explicit.
2. The model has no direct authority to run raw commands.
3. Every operation has a predictable success or failure envelope.
4. Device capabilities are discovered, cached, and checked before execution.
5. Vendor-specific adapters are hidden behind stable network operations.
6. Results are normalized into common shapes.
7. Destructive or high-risk actions require confirmation.

## First Operation Shape

```text
network.<resource-path>.<action>(target="device-or-selector", params...)
```

`resource-path` is one or more dotted identifiers. This keeps simple resources
and nested resources in the same model.

Examples:

```text
network.neighbors.list(target="tower-router-01")
network.interfaces.get(target="core-sw-01", name="ether1")
network.firewall.rules.create(target="edge-01", rule={...})
network.routes.list(target="branch-router-02", table="main")
network.config.backup(target="ap-south-03")
```

## Quick Start

Use the library directly:

```python
from network_lang import network, parse_text, validate_operation

operation = network.interfaces.get(target="core-sw-01", name="ether1")
diagnostics = validate_operation(operation)

operations = parse_text('network.neighbors.list(target="tower-router-01")')
```

Build an operation from a dotted API-style name when dynamic dispatch is easier:

```python
from network_lang import build_operation

operation = build_operation(
    "network.firewall.rules.create",
    target="edge-01",
    rule={"chain": "forward", "action": "drop"},
)
```

Execute a MikroTik RouterOS operation through the vendored REST client:

```python
from network_lang import build_operation
from network_lang.adapters import RouterOSExecutor, RouterOSRestTransport
from network_lang.adapters.ros import Ros

operation = build_operation("network.system.identity.get", target="edge-01")

ros = Ros("https://192.168.88.1/", "admin", "password", secure=False)
result = RouterOSExecutor(RouterOSRestTransport(ros)).execute(operation)

if result.ok:
    print(result.data)
else:
    print(result.error)
```

Compare source-of-truth inventory with live observations:

```python
from network_lang import DeviceRecord, reconcile_devices

expected = [
    DeviceRecord(name="edge-01", host="192.168.88.1"),
    DeviceRecord(name="tower-ap-01", mac="AA:BB:CC:DD:EE:01"),
]

observed = [
    DeviceRecord(name="edge-01-live", host="192.168.88.1"),
    DeviceRecord(name="unknown-cpe", host="10.20.30.45"),
]

report = reconcile_devices(expected, observed)

print(report.unknown_observed)
print(report.missing_expected)
```

Preflight a risky interface change against live topology observations:

```python
from network_lang import (
    AttachmentRecord,
    DeviceRecord,
    build_operation,
    preflight_interface_operation,
)

operation = build_operation(
    "network.interfaces.disable",
    target="poe-switch-01",
    name="ether1",
)

expected = [
    AttachmentRecord(
        DeviceRecord(name="device1", mac="AA:BB:CC:DD:EE:01"),
        "poe-switch-01",
        "ether1",
    ),
    AttachmentRecord(
        DeviceRecord(name="device2", mac="AA:BB:CC:DD:EE:02"),
        "poe-switch-01",
        "ether1",
    ),
]

observed = [
    AttachmentRecord(
        DeviceRecord(name="device1-live", mac="AA-BB-CC-DD-EE-01"),
        "poe-switch-01",
        "ether1",
    ),
    AttachmentRecord(
        DeviceRecord(name="device2-live", mac="AA-BB-CC-DD-EE-02"),
        "poe-switch-01",
        "ether4",
    ),
]

preflight = preflight_interface_operation(operation, expected, observed)
print(preflight.risks)
```

Use flow samples as passive topology evidence:

```python
from network_lang import (
    FlowObservation,
    flow_observations_to_attachments,
    resolve_flow_target,
)

flows = [
    FlowObservation(
        exporter="tower-nas-03",
        src_host="10.20.30.45",
        dst_host="8.8.8.8",
        ingress_interface="pppoe-customer0172",
        egress_interface="uplink-core",
        bytes=12000,
        packets=40,
        src_identifiers=("radius:user/customer0172",),
    )
]

observed = flow_observations_to_attachments(flows)
target = resolve_flow_target("ip:10.20.30.45", flows)
```

The CLI is a thin wrapper around the library and is useful for local checks.

Validate the example operation file:

```sh
python3 -m network_lang validate examples/operations.uns
```

Print parsed operations as JSON:

```sh
python3 -m network_lang parse examples/operations.uns
```

Run the test suite:

```sh
python3 -m unittest discover -s tests
```

## Current Documents

- [Syntax v0](docs/syntax-v0.md)
- [Example operations](examples/operations.uns)
