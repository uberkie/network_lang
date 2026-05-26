# Inventory and Targets

Targets connect vendor-neutral operation names to concrete devices and
execution contexts.

## Default Inventory

By default, inventory is loaded from:

```text
network_lang/data/inventory.json
```

The path is resolved from the current working directory. Override it with the
`NETWORK_LANG_INVENTORY` environment variable or by passing
`inventory_path=...`.

```python
from network_lang import load_inventory

records = load_inventory("path/to/inventory.json")
```

Inventory files must contain a JSON list of objects.

## Record Shape

RouterOS target records commonly include:

```json
{
  "name": "edge-01",
  "url": "https://192.168.88.1/",
  "username": "admin",
  "password": "password",
  "vendor": "mikrotik",
  "platform": "routeros",
  "transport": "rest",
  "secure": false
}
```

Only `url` is required after a target is resolved. If omitted, these defaults
are used:

| Field | Default |
| --- | --- |
| `vendor` | `mikrotik` |
| `platform` | `routeros` |
| `transport` | `rest` |
| `username` | `admin` |
| `password` | `admin` |
| `secure` | `false`, unless `secure=True` is passed |

Do not commit real production passwords into the sample inventory. Use a local
inventory file outside the repository or supply secrets from your own runtime
environment.

## Target Resolution

`resolve_target()` matches a requested target against these record fields:

```text
name, url, id, host, hostname, address
```

```python
from network_lang import resolve_target

record = resolve_target(
    "edge-01",
    inventory=[
        {
            "name": "edge-01",
            "url": "https://192.0.2.1/",
        }
    ],
)
```

If no record matches, `TargetResolutionError` is raised.

## TargetDevice

`target_device()` resolves a target and builds an adapter-backed
`TargetDevice`.

```python
from network_lang import target_device

device = target_device("edge-01", inventory_path="inventory.local.json")
print(device.to_dict())
```

The object exposes a small convenience API:

| Method | Use |
| --- | --- |
| `operation(name, **params)` | Build an operation targeted at this device. |
| `execute(operation)` | Execute an already-built operation. |
| `collect_topology()` | Collect RouterOS topology observations. |
| `preflight(operation, **params)` | Collect topology and preflight an operation. |

Example:

```python
from network_lang import target_device

device = target_device("edge-01")

operation = device.operation("network.interfaces.disable", name="ether2")
result = device.execute(operation)
```

## Supported Target Type

The current target factory only creates RouterOS REST devices. A record must
resolve to:

```text
vendor=mikrotik or routeros
platform=routeros
transport=rest
```

Other adapters can still be planned directly through their adapter functions,
but they are not yet wired into `target_device()`.

