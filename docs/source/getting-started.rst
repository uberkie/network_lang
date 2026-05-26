Getting Started
===============

This guide shows the fastest path from a fresh checkout to parsing,
validating, and planning a network operation.

Install for Local Development
-----------------------------

From the repository root:

.. code-block:: sh

   python3 -m pip install -e .

This installs the ``network_lang`` package and the ``uns`` console script.

Parse an Operation File
-----------------------

``examples/operations.uns`` contains sample operations in the text syntax.

.. code-block:: sh

   uns parse examples/operations.uns

The output is JSON. Each parsed operation includes its dotted name, namespace,
resource path, action, target, risk classification, params, and source line.

Validate an Operation File
--------------------------

.. code-block:: sh

   uns validate examples/operations.uns

Validation checks the reference operation shape:

* the namespace must be ``network``
* the operation must include at least one resource segment and an action
* the action must be one of the core actions
* ``target`` must be present and must be a non-empty string

If the first CLI argument is a file path, ``uns`` defaults to ``validate``:

.. code-block:: sh

   uns examples/operations.uns

Build Operations in Python
--------------------------

Use the fluent builder when the operation name is known in code:

.. code-block:: python

   from network_lang import network

   operation = network.interfaces.get(target="core-sw-01", name="ether1")

Use :func:`network_lang.build_operation` when the operation name is dynamic:

.. code-block:: python

   from network_lang import build_operation

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

Validate before planning or execution:

.. code-block:: python

   from network_lang import validate_operation

   diagnostics = validate_operation(operation)
   if diagnostics:
       for diagnostic in diagnostics:
           print(diagnostic.level, diagnostic.message)

Plan a RouterOS Operation
-------------------------

Planning translates a vendor-neutral operation into RouterOS REST steps without
making network calls.

.. code-block:: python

   from network_lang import build_operation
   from network_lang.adapters import plan_routeros_operation

   operation = build_operation(
       "network.interfaces.disable",
       target="edge-01",
       name="ether2",
   )
   plan = plan_routeros_operation(operation)

   print(plan.capability)
   for step in plan.steps:
       print(step.name, step.method, step.path, step.params, step.body)

Disabling by interface name produces a lookup step followed by a patch step,
because RouterOS REST mutations need an internal resource id.

Execute Through an Inventory Target
-----------------------------------

``target_device()`` resolves an inventory record and returns a
:class:`network_lang.TargetDevice` with an executor already attached.

.. code-block:: python

   from network_lang import target_device

   device = target_device("edge-01")
   result = device.execute(device.operation("network.system.identity.get"))

   if result.ok:
       print(result.data)
   else:
       print(result.error.code, result.error.message)

See :doc:`inventory` for target resolution details.

Run Tests
---------

.. code-block:: sh

   python3 -m unittest discover -s tests

Build These Docs
----------------

From the repository root:

.. code-block:: sh

   cd docs
   make html

The generated site is written to ``docs/build/html``.
