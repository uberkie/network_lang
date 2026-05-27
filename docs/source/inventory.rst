Inventory and Targets
=====================

Targets connect vendor-neutral operation names to concrete devices and
execution contexts.

Default Inventory
-----------------

By default, inventory is loaded from:

::

   network_lang/data/inventory.json

The path is resolved from the current working directory. Override it with the
``NETWORK_LANG_INVENTORY`` environment variable or by passing
``inventory_path=...``.

.. code-block:: python

   from network_lang import load_inventory

   records = load_inventory("path/to/inventory.json")

Inventory files must contain a JSON list of objects.

Record Shape
------------

RouterOS target records commonly include:

.. code-block:: json

   {
     "name": "edge-01",
     "url": "https://192.0.2.10/",
     "username": "admin",
     "password": "change-me",
     "vendor": "mikrotik",
     "platform": "routeros",
     "transport": "rest",
     "secure": false
   }

Only ``url`` is required after a target is resolved. If omitted, these defaults
are used:

.. list-table::
   :header-rows: 1

   * - Field
     - Default
   * - ``vendor``
     - ``mikrotik``
   * - ``platform``
     - ``routeros``
   * - ``transport``
     - ``rest``
   * - ``username``
     - ``admin``
   * - ``password``
     - empty string
   * - ``secure``
     - ``false``, unless ``secure=True`` is passed

Do not commit real production passwords into the sample inventory. Use a local
inventory file outside the repository or supply secrets from your own runtime
environment.

Target Resolution
-----------------

``resolve_target()`` matches a requested target against these record fields:

::

   name, url, id, host, hostname, address

.. code-block:: python

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

If no record matches, :class:`network_lang.TargetResolutionError` is raised.

TargetDevice
------------

``target_device()`` resolves a target and builds an adapter-backed
:class:`network_lang.TargetDevice`.

.. code-block:: python

   from network_lang import target_device

   device = target_device("edge-01", inventory_path="inventory.local.json")
   print(device.to_dict())

The object exposes a small convenience API:

.. list-table::
   :header-rows: 1

   * - Method
     - Use
   * - ``operation(name, **params)``
     - Build an operation targeted at this device.
   * - ``execute(operation)``
     - Execute an already-built operation.
   * - ``collect_topology()``
     - Collect RouterOS topology observations.
   * - ``preflight(operation, **params)``
     - Collect topology and preflight an operation.
   * - ``graph(operation_name, **params)``
     - Collect operation samples and build an adapter-normalized graph.

Example:

.. code-block:: python

   from network_lang import target_device

   device = target_device("edge-01")

   operation = device.operation("network.interfaces.disable", name="ether2")
   result = device.execute(operation)

Supported Target Type
---------------------

The current target factory only creates RouterOS REST devices. A record must
resolve to:

.. code-block:: text

   vendor=mikrotik or routeros
   platform=routeros
   transport=rest

Other adapters can still be planned directly through their adapter functions,
but they are not yet wired into ``target_device()``.
