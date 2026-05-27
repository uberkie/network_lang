# Topology, Reconciliation, and Preflight

Topology helpers answer a practical question before risky changes:

```text
Does the operation target the interface we think it targets, and what live
devices are currently observed there?
```

## Device Records

`DeviceRecord` represents a device as seen in inventory, RouterOS neighbor
data, ARP tables, bridge host tables, or flow records.

```python
from network_lang import DeviceRecord

device = DeviceRecord(
    name="customer-cpe-01",
    host="10.20.30.45",
    mac="AA:BB:CC:DD:EE:01",
    identifiers=("radius:user/customer0172",),
)
```

Matching uses normalized identity keys:

- `name:<name>`
- `host:<host>`
- `mac:<mac>`
- `serial:<serial>`
- any explicit `identifiers`

MAC addresses are normalized across common separator styles. IP addresses are
normalized with Python's `ipaddress` module.

## Device Reconciliation

```python
from network_lang import DeviceRecord, reconcile_devices

expected = [
    DeviceRecord(name="edge-01", host="192.168.88.1"),
]

observed = [
    DeviceRecord(name="edge-01-live", host="192.168.88.1"),
    DeviceRecord(name="unknown-cpe", host="10.20.30.45"),
]

report = reconcile_devices(expected, observed)
print(report.ok)
print(report.matches)
print(report.unknown_observed)
print(report.missing_expected)
```

`report.ok` is true when there are no unknown observed devices and no missing
expected devices.

## Attachment Records

`AttachmentRecord` adds a network location to a `DeviceRecord`.

```python
from network_lang import AttachmentRecord, DeviceRecord

attachment = AttachmentRecord(
    device=DeviceRecord(name="customer-cpe-01", mac="AA:BB:CC:DD:EE:01"),
    network_device="poe-switch-01",
    interface="ether2",
    source="inventory",
)
```

Attachments match by device identity and compare by location:

```text
network_device + interface + optional scope
```

This is how the library detects that a known device moved from one port to
another.

## Attachment Reconciliation

```python
from network_lang import AttachmentRecord, DeviceRecord, reconcile_attachments

expected = [
    AttachmentRecord(
        DeviceRecord(name="cpe-01", mac="AA:BB:CC:DD:EE:01"),
        "poe-switch-01",
        "ether1",
    )
]

observed = [
    AttachmentRecord(
        DeviceRecord(mac="AA-BB-CC-DD-EE-01"),
        "poe-switch-01",
        "ether4",
    )
]

report = reconcile_attachments(expected, observed)
print(report.moved)
```

The report contains:

| Field | Meaning |
| --- | --- |
| `matches` | Expected and observed device are on the same location. |
| `moved` | Same device identity, different location. |
| `unknown_observed` | Observed device was not expected. |
| `missing_expected` | Expected device was not observed. |
| `duplicate_observed` | Same identity key was seen in multiple locations. |

## Interface State Records

`InterfaceStateRecord` captures whether an interface appears disabled,
inactive, running, forwarding, or in another adapter-specific status.

```python
from network_lang import InterfaceStateRecord

state = InterfaceStateRecord(
    network_device="poe-switch-01",
    interface="ether2",
    scope="bridge1",
    inactive=True,
    running=False,
    status="inactive",
)
```

RouterOS bridge port rows can be normalized into interface states with
`routeros_bridge_ports_to_interface_states()`.

## Preflight an Interface Operation

`preflight_interface_operation()` compares the operation target interface
against expected attachments, observed attachments, and optional interface
state.

```python
from network_lang import (
    AttachmentRecord,
    DeviceRecord,
    InterfaceStateRecord,
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
        DeviceRecord(name="cpe-01", mac="AA:BB:CC:DD:EE:01"),
        "poe-switch-01",
        "ether1",
    )
]

observed = [
    AttachmentRecord(
        DeviceRecord(mac="AA-BB-CC-DD-EE-01"),
        "poe-switch-01",
        "ether4",
    )
]

states = [
    InterfaceStateRecord(
        "poe-switch-01",
        "ether1",
        inactive=True,
        status="inactive",
    )
]

report = preflight_interface_operation(operation, expected, observed, states)
print(report.ok)
print(report.risks)
```

Risks include:

- expected devices observed on a different interface
- unknown live devices on the target interface
- expected devices missing from the target interface
- duplicate observed identity keys
- disabled, inactive, or non-running interface state

## Live RouterOS Preflight

With a resolved target, RouterOS topology collection and preflight can be
handled through `TargetDevice`.

```python
from network_lang import target_device

device = target_device("edge-01")
result = device.preflight("network.interfaces.disable", name="ether2")

if result.ok:
    print("preflight clear")
else:
    print(result.error.code)
    print(result.data.risks)
```

Internally, this collects RouterOS neighbors and bridge ports, normalizes them,
and then runs the same preflight logic.

## Flow Observations

`FlowObservation` can turn passive flow samples into device or attachment
evidence.

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
        protocol="udp",
        dst_port=53,
        bytes=12000,
        packets=40,
        src_identifiers=("radius:user/customer0172",),
    )
]

attachments = flow_observations_to_attachments(flows)
target = resolve_flow_target("ip:10.20.30.45", flows)
```

`resolve_flow_target()` returns the best matching observation with network
device, interface, direction, and confidence.


## Documentation

- [Sphinx documentation index](docs/source/index.rst)
- [Getting started](getting-started.md)
- [Operation model](docs/operations.md)
- [Adapters](docs/adapters.md)
- [Inventory and targets](docs/inventory.md)
- [Topology, reconciliation, and preflight](docs/topology-preflight.md)
- [Flow collector](docs/flowcollector.md)
- [Syntax v0 reference](docs/syntax-v0.md)
- [Example operations](examples/operations.uns)
