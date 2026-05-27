# Unified Network Syntax

The engineer’s job is to solve network problems, not repeatedly rebuild fragile tooling around already-solved access patterns. Unified Network Syntax treats SSH, API, SNMP, NETCONF, flow samples, and parser fallbacks as adapter concerns, so the operator can focus on intent, reconciliation, and safe action.

Unified Network Syntax is a small Python reference implementation for a
vendor-neutral network operation model. It lets operators describe intent once,
validate that intent, and then translate it to device-specific adapters such as
MikroTik RouterOS REST or Ubiquiti airOS endpoint plans.

The project is library-first. Text files and the `uns` CLI are convenient ways
to parse and inspect the same operation model, but the core object is always an
`Operation`.

```text
operator intent
  -> unified operation
  -> validation and capability planning
  -> adapter execution or endpoint plan
  -> normalized result
```

## What Works Today

- Parse `.uns` operation files into typed Python `Operation` objects.
- Build operations from Python with either fluent attribute access or dotted
  operation names.
- Validate namespaces, operation shape, core actions, and required targets.
- Plan and execute selected MikroTik RouterOS REST operations.
- Plan selected Ubiquiti airOS operations without executing them.
- Normalize RouterOS neighbor, ARP, bridge host, and bridge port data into
  inventory and topology records.
- Reconcile expected devices or attachments against observed data.
- Preflight risky interface operations against live or supplied topology
  observations.
- Convert NetFlow-like observations into topology evidence.

## Install

Use an editable install while developing:

```sh
python3 -m pip install -e .
```

The package exposes the `uns` console script and can also be run as a module:

```sh
uns validate examples/operations.uns
python3 -m network_lang parse examples/operations.uns
```

## Quick Example

```python
from network_lang import build_operation, validate_operation
from network_lang.adapters import plan_routeros_operation

operation = build_operation(
    "network.firewall.rules.create",
    target="edge-01",
    rule={
        "chain": "forward",
        "action": "drop",
        "src": "10.20.30.0/24",
        "dst": "0.0.0.0/0",
    },
)

diagnostics = validate_operation(operation)
if diagnostics:
    raise ValueError(diagnostics[0].message)

plan = plan_routeros_operation(operation)
for step in plan.steps:
    print(step.method, step.path, step.body)
```

## Operation Shape

Operations use a dotted name and keyword parameters:

```text
network.<resource-path>.<action>(target="device-or-selector", params...)
```

Examples:

```text
network.neighbors.list(target="tower-router-01")
network.interfaces.get(target="core-sw-01", name="ether1")
network.firewall.rules.create(target="edge-01", rule={chain="forward", action="drop"})
network.routes.list(target="branch-router-02", table="main")
network.system.identity.get(target="ap-south-03")
```

The currently recognized core actions are:

```text
list get create update delete enable disable observe run backup diff validate
```

## Python API

Build operations with the fluent API:

```python
from network_lang import network

operation = network.interfaces.get(target="core-sw-01", name="ether1")
print(operation.name)  # network.interfaces.get
```

Or build them dynamically:

```python
from network_lang import build_operation

operation = build_operation(
    "network.interfaces.disable",
    target="core-sw-01",
    name="ether24",
)
```

Parse `.uns` text:

```python
from network_lang import parse_text

operations = parse_text('network.neighbors.list(target="tower-router-01")')
```

## CLI

Validate operation files:

```sh
uns validate examples/operations.uns
```

Print parsed operations as JSON:

```sh
uns parse examples/operations.uns
```

If the first argument is a file path, `uns` defaults to `validate`:

```sh
uns examples/operations.uns
```

## RouterOS Execution

`target_device()` resolves a target from inventory, creates a RouterOS REST
executor, and hides the adapter wiring behind a small device object.

```python
from network_lang import target_device

device = target_device("edge-01")
result = device.execute(
    device.operation("network.system.identity.get")
)

if result.ok:
    print(result.data)
else:
    print(result.error.message)
```

By default, inventory is loaded from `network_lang/data/inventory.json` under
the current working directory. Set `NETWORK_LANG_INVENTORY` or pass
`inventory_path=...` to use another file.

## Topology Preflight

Topology helpers let you check whether a risky interface operation lines up
with the devices currently observed on that interface.

```python
from network_lang import target_device

device = target_device("edge-01")
preflight = device.preflight(
    "network.interfaces.disable",
    name="ether2",
)

if not preflight.ok:
    print(preflight.data.risks)
```

## Documentation

- [Sphinx documentation index](docs/source/index.rst)
- [Getting started](docs/source/getting-started.rst)
- [Operation model](docs/source/operations.rst)
- [Adapters](docs/source/adapters.rst)
- [Inventory and targets](docs/source/inventory.rst)
- [Topology, reconciliation, and preflight](docs/source/topology-preflight.rst)
- [Syntax v0 reference](docs/source/syntax-v0.rst)
- [Example operations](examples/operations.uns)

Build the HTML docs with:

```sh
cd docs
make html
```

## Tests

Run the test suite with:

```sh
python3 -m unittest discover -s tests
```
