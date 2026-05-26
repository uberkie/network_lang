# Syntax v0

This document defines the first draft of the unified network syntax. It is
intentionally small: enough to test the idea without locking the project into a
large framework too early.

## Thesis

Basic network management operations are already present across many interfaces.
The problem is not whether devices can be controlled. The problem is that every
interface expresses control differently.

Unified Network Syntax normalizes intent above the transport layer.

## Architecture

```text
Intent layer
  -> operation parser
  -> capability resolver
  -> policy guard
  -> adapter selector
  -> executor
  -> normalizer
  -> result envelope
```

## Operation Format

```text
network.<domain>.<resource>.<action>(target, params)
```

Where:

- `network` is the root namespace.
- `domain` is the operational area, such as `interfaces`, `neighbors`,
  `routes`, `firewall`, `wireless`, `config`, or `system`.
- `resource` is the thing being operated on.
- `action` is the requested operation.
- `target` identifies a device, group, inventory selector, or connection
  profile.
- `params` contains typed input for the adapter.

## Core Actions

The syntax starts with common operation verbs:

```text
list      read many resources
get       read one resource
create    create a resource
update    modify a resource
delete    remove a resource
enable    enable an existing resource
disable   disable an existing resource
run       execute a bounded operational action
backup    export or snapshot config/state
diff      compare desired and actual state
validate  check whether an operation could run
```

CRUD is useful, but networks also need `observe`, `execute`, `validate`, and
`backup` style operations.

## Capability States

Every operation must resolve to one of these states before execution:

```text
supported
unsupported
supported_via_fallback
read_only
requires_confirmation
requires_vendor_adapter
partial
unknown
```

The system should fail before execution if a required capability is missing.

## Result Envelope

Every adapter returns the same top-level result shape:

```json
{
  "ok": true,
  "operation": "network.neighbors.list",
  "target": "tower-router-01",
  "capability": "supported_via_fallback",
  "adapter": {
    "vendor": "mikrotik",
    "transport": "ssh",
    "name": "routeros-ssh-neighbors"
  },
  "data": [],
  "warnings": [],
  "error": null,
  "raw_ref": "artifact://runs/2026-05-26/abc123/raw.txt"
}
```

Failures use the same shape:

```json
{
  "ok": false,
  "operation": "network.firewall.rules.create",
  "target": "edge-01",
  "capability": "read_only",
  "adapter": null,
  "data": null,
  "warnings": [],
  "error": {
    "code": "CAPABILITY_NOT_SUPPORTED",
    "message": "Target only supports firewall rule reads through this profile.",
    "retryable": false
  },
  "raw_ref": null
}
```

## Adapter Contract

Adapters translate the operation into the best supported backend:

```text
MikroTik API       -> RouterOS API sentence/path
MikroTik SSH       -> CLI command plus parser
Cisco NETCONF      -> YANG/XML edit-config or get
RESTCONF device    -> HTTP request against YANG-modeled resource
SNMP device        -> GET/SET OID where supported
Ubiquiti airOS     -> SSH or HTTP parser fallback
Linux host         -> iproute2/nftables/system command wrapper
Ansible            -> bounded executor backend, not top-level syntax
```

Each adapter must provide:

- capability probe
- input schema
- transport implementation
- output normalizer
- error mapper
- risk level

## Safety Model

Operations are grouped by risk:

```text
read       no state change
observe    active but non-mutating probe
write      modifies config or state
destructive deletes, disables, resets, or interrupts service
secret     touches credentials, keys, or private config
```

`write`, `destructive`, and `secret` operations require explicit policy checks.

## Open Questions

1. Should the syntax be primarily function-like, JSON/YAML, or both?
2. Should `target` be a single string, inventory selector, or typed object?
3. How much should the project reuse existing YANG models?
4. Should the first prototype target one vendor first, such as MikroTik?
5. Should adapters be local plugins, remote tools, or both?

