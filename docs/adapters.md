# Adapters

Adapters translate the neutral `Operation` model into vendor-specific calls,
plans, and normalized results.

## RouterOS REST

The RouterOS adapter can plan and execute selected MikroTik RouterOS REST
operations.

```python
from network_lang import build_operation
from network_lang.adapters import RouterOSExecutor, RouterOSRestTransport
from network_lang.adapters.rosapi import Ros

operation = build_operation("network.system.identity.get", target="edge-01")

ros = Ros("https://192.168.88.1/", "admin", "password", secure=False)
transport = RouterOSRestTransport(ros)
result = RouterOSExecutor(transport).execute(operation)
```

### Supported Operation Mappings

| Operation | RouterOS REST path | Behavior |
| --- | --- | --- |
| `network.system.identity.get` | `/system/identity` | `GET` |
| `network.neighbors.list` | `/ip/neighbor` | `GET` with optional `match` filters |
| `network.bridge.hosts.list` | `/interface/bridge/host` | `GET` with optional `match` filters |
| `network.bridge.ports.list` | `/interface/bridge/port` | `GET` with optional `match` filters |
| `network.bridge.ports.create` | `/interface/bridge/port` | `PUT` with `port` or `data` body |
| `network.interfaces.list` | `/interface` | `GET` with optional `match` filters |
| `network.interfaces.get` | `/interface` | `GET`, adding `name` as a filter when supplied |
| `network.interfaces.disable` | `/interface` | `PATCH` by `id`, or lookup by `name`/`match` then patch |
| `network.interfaces.enable` | `/interface` | `PATCH` by `id`, or lookup by `name`/`match` then patch |
| `network.routes.list` | `/ip/route` | `GET` with optional `match` filters |
| `network.routes.create` | `/ip/route` | `PUT` with `route` or `data` body |
| `network.firewall.rules.list` | `/ip/firewall/filter` | `GET` with optional `match` filters |
| `network.firewall.rules.create` | `/ip/firewall/filter` | `PUT` with `rule` or `data` body |
| `network.addresses.list` | `/ip/address` | `GET` with optional `match` filters |
| `network.addresses.create` | `/ip/address` | `PUT` with `address` or `data` body |
| `network.vlans.create` | `/interface/vlan` | `PUT` with `vlan` or `data` body |
| `network.vlans.update` | `/interface/vlan` | `PATCH` by `id`, or lookup by `name`/`match` then patch |
| `network.wireless.clients.list` | `/interface/wireless/registration-table` | `GET` with optional `match` filters |

Unsupported operations return an `OperationResult` with:

```text
ok=False
capability="unsupported"
error.code="UNSUPPORTED_OPERATION"
```

### Planning Without Execution

```python
from network_lang import build_operation
from network_lang.adapters import plan_routeros_operation

operation = build_operation("network.interfaces.disable", target="edge-01", name="ether2")
plan = plan_routeros_operation(operation)

print(plan.capability)
print(plan.warnings)
```

Disabling or enabling by `id` is a direct patch:

```python
build_operation("network.interfaces.disable", target="edge-01", id="*2")
```

Disabling or enabling by `name` or `match` requires a read-before-write lookup:

```python
build_operation("network.interfaces.disable", target="edge-01", name="ether2")
build_operation(
    "network.interfaces.disable",
    target="edge-01",
    match={"name": "ether2"},
)
```

That plan has capability `supported_via_fallback` and includes a warning.

### Key Translation

For common RouterOS resources, neutral snake-case keys are translated to
RouterOS REST keys:

| Neutral key | RouterOS key |
| --- | --- |
| `dst`, `dst_address` | `dst-address` |
| `table`, `routing_table` | `routing-table` |
| `pref_src` | `pref-src` |
| `check_gateway` | `check-gateway` |
| `src`, `src_address` | `src-address` |
| `dst`, `dst_address` | `dst-address` |
| `src_port` | `src-port` |
| `dst_port` | `dst-port` |
| `in_interface` | `in-interface` |
| `out_interface` | `out-interface` |
| `connection_state` | `connection-state` |

Unknown keys are converted from underscores to hyphens.

### Normalizers

RouterOS observation rows can be converted into common records:

| Function | Output |
| --- | --- |
| `routeros_neighbors_to_devices()` | `DeviceRecord` tuple |
| `routeros_neighbors_to_attachments()` | `AttachmentRecord` tuple |
| `routeros_arp_to_devices()` | `DeviceRecord` tuple |
| `routeros_arp_to_attachments()` | `AttachmentRecord` tuple |
| `routeros_bridge_hosts_to_attachments()` | `AttachmentRecord` tuple |
| `routeros_bridge_ports_to_interface_states()` | `InterfaceStateRecord` tuple |

These are used by topology collection and can also be called directly when you
already have RouterOS API output.

## RouterOS Topology Composition

`collect_routeros_topology()` composes two read operations:

```text
network.neighbors.list
network.bridge.ports.list
```

It returns a `RouterOSTopologySnapshot` containing:

- normalized attachments
- normalized interface states
- raw neighbor data
- raw bridge port data

`preflight_routeros_operation()` uses that snapshot to preflight risky
interface operations.

## Ubiquiti airOS Plans

The airOS adapter currently plans endpoint calls. It does not execute HTTP
requests yet.

```python
from network_lang import build_operation
from network_lang.adapters import AirOSEndpoints, plan_airos_operation

endpoints = AirOSEndpoints.from_host("192.168.0.20")
operation = build_operation("network.wireless.clients.list", target="cpe-01")
plan = plan_airos_operation(operation, endpoints)
```

### Supported airOS Plans

| Operation | Endpoint behavior |
| --- | --- |
| `network.system.identity.get` | Login, then `GET /status.cgi` |
| `network.system.status.get` | Login, then `GET /status.cgi` |
| `network.wireless.clients.list` | Login, then `GET /status.cgi` |
| `network.system.warnings.get` | Login, then `GET /api/warnings`, then logout |
| `network.system.reboot.run` | Login, then `POST /reboot.cgi` |
| `network.wireless.clients.delete` | Login, then `POST /stakick.cgi` with `match.mac` |
| `network.system.provisioning.update` | Login, then `POST /api/provmode` with `data.enabled` |
| `network.firmware.update.get` | Login, then `GET /api/fw/update-check` |
| `network.firmware.download.run` | Login, then `POST /api/fw/download` |
| `network.firmware.download_progress.get` | Login, then `GET /api/fw/download-progress` |
| `network.firmware.install.run` | Login, then `POST /fwflash.cgi` |

Firmware major version `6` marks status reads as `supported_via_fallback`
because airOS 6 uses the legacy login path.

Operations that interrupt service, such as reboot and firmware install, include
warnings in the returned plan.

## Documentation

- [Sphinx documentation index](docs/source/index.rst)
- [Getting started](getting-started.md)
- [Operation model](operations.md)
- [Adapters](adapters.md)
- [Inventory and targets](inventory.md)
- [Topology, reconciliation, and preflight](topology-preflight.md)
- [Flow collector](flowcollector.md)
- [Syntax v0 reference](syntax-v0.md)
- [Example operations](examples/operations.uns)
