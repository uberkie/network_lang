Syntax v0 Reference
===================

This page captures the first draft of Unified Network Syntax. It is
intentionally small: enough to test the idea without locking the project into a
large framework too early.

Thesis
------

Basic network management operations are already present across many interfaces.
The problem is not whether devices can be controlled. The problem is that every
interface expresses control differently.

Unified Network Syntax normalizes intent above the transport layer.

Architecture
------------

::

   Application/library call or .uns text
     -> operation parser
     -> capability resolver
     -> policy guard
     -> adapter selector
     -> executor
     -> normalizer
     -> result envelope

Operation Format
----------------

::

   network.<resource-path>.<action>(target="device-or-selector", params...)

Where:

* ``network`` is the root namespace.
* ``resource-path`` is one or more dotted identifiers for the thing being
  operated on.
* ``action`` is the requested operation.
* ``target`` identifies a device, group, inventory selector, or connection
  profile.
* Additional keyword arguments contain typed input for the adapter.

Core Actions
------------

.. code-block:: text

   list      read many resources
   get       read one resource
   create    create a resource
   update    modify a resource
   delete    remove a resource
   enable    enable an existing resource
   disable   disable an existing resource
   observe   run an active but non-mutating observation
   run       execute a bounded operational action
   backup    export or snapshot config/state
   diff      compare desired and actual state
   validate  check whether an operation could run

Value Literals
--------------

The reference parser currently accepts:

.. code-block:: text

   "string" or 'string'
   123, -123, 12.3
   true, false, null
   [value, value]
   { key=value, key=value }

Object keys are bare identifiers. Operation arguments and object fields both
use ``key=value`` syntax.

Capability States
-----------------

Every operation should resolve to one of these states before execution:

.. code-block:: text

   supported
   unsupported
   supported_via_fallback
   read_only
   requires_confirmation
   requires_vendor_adapter
   partial
   unknown

The system should fail before execution if a required capability is missing.

Result Envelope
---------------

Every adapter returns the same top-level result shape:

.. code-block:: json

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

Failures use the same shape with ``ok=false`` and a structured error.

Adapter Contract
----------------

Adapters translate the operation into the best supported backend:

.. code-block:: text

   MikroTik API       -> RouterOS API sentence/path
   MikroTik SSH       -> CLI command plus parser
   Cisco NETCONF      -> YANG/XML edit-config or get
   RESTCONF device    -> HTTP request against YANG-modeled resource
   SNMP device        -> GET/SET OID where supported
   Ubiquiti airOS     -> SSH or HTTP parser fallback
   Linux host         -> iproute2/nftables/system command wrapper
   Ansible            -> bounded executor backend, not top-level syntax

Each adapter must provide capability probes, input schemas, a transport
implementation, output normalizers, error mapping, and a risk level.

Safety Model
------------

Operations are grouped by risk:

.. code-block:: text

   read        no state change
   observe     active but non-mutating probe
   write       modifies config or state
   destructive deletes, disables, resets, or interrupts service
   secret      touches credentials, keys, or private config

``write``, ``destructive``, and ``secret`` operations require explicit policy
checks.

Open Questions
--------------

* Should the syntax be primarily function-like, JSON/YAML, or both?
* Should ``target`` be a single string, inventory selector, or typed object?
* How much should the project reuse existing YANG models?
* Should the first prototype target one vendor first, such as MikroTik?
* Should adapters be local plugins, remote tools, or both?
