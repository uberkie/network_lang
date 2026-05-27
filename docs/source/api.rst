API Reference
=============

This page documents the public API that callers are expected to use. It avoids
dumping adapter internals and derived endpoint properties into the main
reference; the full source remains linked through ``[source]`` where useful.

Import Path Overview
--------------------

Most code should import from ``network_lang`` first:

.. code-block:: python

   from network_lang import (
       build_operation,
       network,
       parse_text,
       target_device,
       validate_operation,
   )

Adapter-specific planning and execution helpers live under
``network_lang.adapters``:

.. code-block:: python

   from network_lang.adapters import (
       RouterOSExecutor,
       RouterOSRestTransport,
       plan_routeros_operation,
       plan_airos_operation,
   )

Core Entry Points
-----------------

.. list-table::
   :header-rows: 1

   * - API
     - Use
   * - :data:`network_lang.network`
     - Fluent operation builder, for example ``network.interfaces.get(...)``.
   * - :func:`network_lang.build_operation`
     - Build an operation from a dotted operation name.
   * - :func:`network_lang.parse_text`
     - Parse one or more text operations.
   * - :func:`network_lang.parse_file`
     - Parse operations from a ``.uns`` file.
   * - :func:`network_lang.validate_operation`
     - Validate a single operation.
   * - :func:`network_lang.validate_operations`
     - Validate a list of operations.
   * - :func:`network_lang.target_device`
     - Resolve inventory and create an adapter-backed target.

Operation Construction
----------------------

.. autodata:: network_lang.network
   :annotation:

.. autofunction:: network_lang.build_operation

.. autoclass:: network_lang.OperationBuilder
   :special-members: __call__

Operation Objects
-----------------

.. autoclass:: network_lang.Operation
   :members: name, target, risk, to_dict

.. autoclass:: network_lang.SourceSpan
   :members: label

Parsing and Validation
----------------------

.. autofunction:: network_lang.parse_text

.. autofunction:: network_lang.parse_file

.. autoexception:: network_lang.ParseError
   :special-members: __str__

.. autofunction:: network_lang.validate_operation

.. autofunction:: network_lang.validate_operations

.. autoclass:: network_lang.Diagnostic
   :members: is_error, label

Results
-------

.. autoclass:: network_lang.OperationResult
   :members: to_dict

.. autoclass:: network_lang.ResultError
   :members: to_dict

Targets and Inventory
---------------------

.. autofunction:: network_lang.target_device

.. autofunction:: network_lang.resolve_target

.. autofunction:: network_lang.load_inventory

.. autofunction:: network_lang.default_inventory_path

.. autofunction:: network_lang.collect_topology

.. autofunction:: network_lang.preflight_operation

.. autoexception:: network_lang.TargetResolutionError

.. autoclass:: network_lang.TargetDevice
   :members: execute, operation, collect_topology, preflight, graph, to_dict

Reconciliation
--------------

.. autofunction:: network_lang.reconcile_devices

.. autoclass:: network_lang.DeviceRecord
   :members: keys, label, to_dict

.. autoclass:: network_lang.DeviceMatch
   :members: to_dict

.. autoclass:: network_lang.ReconciliationReport
   :members: ok, to_dict

Topology and Preflight
----------------------

.. autofunction:: network_lang.reconcile_attachments

.. autofunction:: network_lang.preflight_interface_operation

.. autoclass:: network_lang.AttachmentRecord
   :members: keys, location_key, location_label, to_dict

.. autoclass:: network_lang.InterfaceStateRecord
   :members: location_key, location_label, to_dict

.. autoclass:: network_lang.AttachmentReconciliationReport
   :members: ok, to_dict

.. autoclass:: network_lang.TopologyPreflightReport
   :members: ok, to_dict

Flow Observations
-----------------

.. autofunction:: network_lang.flow_observations_to_devices

.. autofunction:: network_lang.flow_observations_to_attachments

.. autofunction:: network_lang.resolve_flow_target

.. autofunction:: network_lang.classify_flow_device

.. autofunction:: network_lang.flow_records_to_devices

.. autofunction:: network_lang.load_flow_devices

``network_lang.FLOW_RECON_POLICY``
   Default class-to-action mapping used by
   :func:`network_lang.apply_flow_recon_policy`.

.. autofunction:: network_lang.apply_flow_recon_policy

.. autofunction:: network_lang.reconcile_flow_envelope

.. autoclass:: network_lang.FlowReconFinding
   :members: to_dict

.. autoclass:: network_lang.FlowReconPolicyReport
   :members: ok, exit_code, to_dict, to_text

.. autoclass:: network_lang.FlowExpectation
   :members: to_dict

.. autoclass:: network_lang.FlowObservation
   :members: to_dict

.. autoclass:: network_lang.FlowTargetResolution
   :members: to_dict

.. autoclass:: network_lang.FlowSignalCheck
   :members: to_dict

.. autoclass:: network_lang.FlowEnvelopeReport
   :members: ok, to_dict

Graphing and Exporters
----------------------

Simple operator-facing graphs can be built from records and written directly
to standalone HTML files.

.. autofunction:: network_lang.graph_operation

.. autofunction:: network_lang.line_graph

.. autofunction:: network_lang.bar_graph

.. autofunction:: network_lang.counter_rate_records

.. autofunction:: network_lang.counter_rate_field_name

.. autofunction:: network_lang.to_html

.. autoclass:: network_lang.LineGraph
   :members: to_dict

.. autoclass:: network_lang.BarGraph
   :members: to_dict

.. autoclass:: network_lang.GraphSeries
   :members: to_dict

.. autoclass:: network_lang.GraphPoint
   :members: to_dict

RouterOS Adapter
----------------

Use these when planning or executing RouterOS REST operations directly.

.. autofunction:: network_lang.adapters.plan_routeros_operation

.. autofunction:: network_lang.adapters.execute_routeros_operation

.. autofunction:: network_lang.adapters.collect_routeros_topology

.. autofunction:: network_lang.adapters.preflight_routeros_operation

.. autoclass:: network_lang.adapters.RouterOSExecutor
   :members: execute, execute_plan

.. autoclass:: network_lang.adapters.RouterOSRestTransport
   :members: request

.. autoclass:: network_lang.adapters.RouterOSPlan
   :members: supported

.. autoclass:: network_lang.adapters.RouterOSPlanStep

.. autoclass:: network_lang.adapters.RouterOSTopologySnapshot
   :members: to_dict

RouterOS Normalizers
~~~~~~~~~~~~~~~~~~~~

.. autofunction:: network_lang.adapters.routeros_neighbors_to_devices

.. autofunction:: network_lang.adapters.routeros_neighbors_to_attachments

.. autofunction:: network_lang.adapters.routeros_arp_to_devices

.. autofunction:: network_lang.adapters.routeros_arp_to_attachments

.. autofunction:: network_lang.adapters.routeros_bridge_hosts_to_attachments

.. autofunction:: network_lang.adapters.routeros_bridge_ports_to_interface_states

airOS Adapter
-------------

The airOS adapter currently exposes endpoint planning. The detailed endpoint
URL properties are intentionally omitted from this page; see
:doc:`adapters` for the supported operation matrix.

.. autofunction:: network_lang.adapters.plan_airos_operation

.. autoclass:: network_lang.adapters.AirOSEndpoints
   :members: from_host

.. autoclass:: network_lang.adapters.AirOSPlan
   :members: supported

.. autoclass:: network_lang.adapters.AirOSPlanStep
