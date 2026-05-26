Operation Model
===============

The operation model is the stable shape that the parser, CLI, validators, and
adapters share.

::

   network.<resource-path>.<action>(target="device-or-selector", params...)

Examples:

.. code-block:: text

   network.neighbors.list(target="tower-router-01")
   network.interfaces.get(target="core-sw-01", name="ether1")
   network.firewall.rules.create(target="edge-01", rule={chain="forward", action="drop"})
   network.routes.list(target="branch-router-02", table="main")
   network.system.identity.get(target="ap-south-03")

Operation Fields
----------------

.. list-table::
   :header-rows: 1

   * - Field
     - Meaning
   * - ``namespace``
     - Root namespace. The reference validator expects ``network``.
   * - ``resource_path``
     - Resource segments, such as ``("firewall", "rules")``.
   * - ``action``
     - Final verb, such as ``list``, ``get``, ``create``, or ``disable``.
   * - ``params``
     - Keyword arguments supplied to the operation.
   * - ``source``
     - Optional source location when parsed from text.
   * - ``name``
     - Dotted full name, such as ``network.interfaces.get``.
   * - ``target``
     - Shortcut for ``params["target"]`` when present.
   * - ``risk``
     - Risk class inferred from the action.

Core Actions
------------

The reference validator accepts these actions:

.. list-table::
   :header-rows: 1

   * - Action
     - Risk
     - Use
   * - ``list``
     - ``read``
     - Read many resources.
   * - ``get``
     - ``read``
     - Read one resource.
   * - ``backup``
     - ``read``
     - Export or snapshot config/state.
   * - ``diff``
     - ``read``
     - Compare desired and actual state.
   * - ``validate``
     - ``read``
     - Check whether an operation could run.
   * - ``observe``
     - ``observe``
     - Run an active but non-mutating observation.
   * - ``run``
     - ``observe``
     - Run a bounded operational action.
   * - ``create``
     - ``write``
     - Create a resource.
   * - ``update``
     - ``write``
     - Modify a resource.
   * - ``enable``
     - ``write``
     - Enable an existing resource.
   * - ``delete``
     - ``destructive``
     - Remove a resource.
   * - ``disable``
     - ``destructive``
     - Disable an existing resource.

Unknown actions are allowed by the parser but rejected by validation.

Text Syntax
-----------

The parser accepts one or more operation calls. Calls can span multiple lines.
Comments start with ``#`` outside quoted strings.

.. code-block:: text

   # Read an interface
   network.interfaces.get(target="core-sw-01", name="ether1")

   # Create a firewall rule
   network.firewall.rules.create(
     target="edge-01",
     rule={
       chain="forward",
       action="drop",
       src="10.20.30.0/24",
       dst="0.0.0.0/0"
     }
   )

Value literals:

.. list-table::
   :header-rows: 1

   * - Literal
     - Example
   * - String
     - ``"edge-01"`` or ``'edge-01'``
   * - Integer
     - ``123``
   * - Float
     - ``12.3``
   * - Boolean
     - ``true`` or ``false``
   * - Null
     - ``null``
   * - List
     - ``[80, 443]``
   * - Object
     - ``{chain="forward", action="drop"}``

Object keys and operation argument names are bare identifiers. They use
``key=value`` syntax.

Python Builders
---------------

Fluent builder:

.. code-block:: python

   from network_lang import network

   operation = network.system.identity.get(target="edge-01")

Dotted-name builder:

.. code-block:: python

   from network_lang import build_operation

   operation = build_operation("network.system.identity.get", target="edge-01")

Both builders produce the same :class:`network_lang.Operation` shape.

Validation
----------

.. code-block:: python

   from network_lang import parse_text, validate_operations

   operations = parse_text('network.interfaces.get(target="edge-01", name="ether1")')
   diagnostics = validate_operations(operations)

Each diagnostic has a level, message, operation, ``is_error`` boolean, and
``label()`` method for source locations such as
``examples/operations.uns:4:1``.

Result Envelope
---------------

Adapters return :class:`network_lang.OperationResult`.

.. list-table::
   :header-rows: 1

   * - Field
     - Meaning
   * - ``ok``
     - ``True`` when execution or composition succeeded.
   * - ``operation``
     - Operation name.
   * - ``target``
     - Operation target.
   * - ``capability``
     - Adapter capability result, such as ``supported`` or ``unsupported``.
   * - ``adapter``
     - Adapter metadata, or ``None`` when not applicable.
   * - ``data``
     - Normalized result data.
   * - ``warnings``
     - Non-fatal warnings.
   * - ``error``
     - :class:`network_lang.ResultError` when ``ok`` is false.
   * - ``raw_ref``
     - Optional reference to raw output artifacts.

Use ``result.to_dict()`` when returning or printing results as JSON-like data.
