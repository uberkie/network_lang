# Unified Network Syntax

This repository is a starting point for an abstracted network operation syntax:
a vendor-neutral intent layer that can map the same operator action onto
different device interfaces such as SSH, REST, NETCONF, RESTCONF, SNMP,
RouterOS API, vendor SDKs, and parser fallbacks.

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
