Flow Collector
==============

``flowcollector`` is a lightweight Go daemon for extracting basic NetFlow data
into JSONL device records. It does not analyze, enrich, or score traffic. Its
job is only to receive flow packets, decode the default fields, and emit records
that the Python reconciliation layer can consume.

The first implementation supports NetFlow v5 over UDP.

Build
-----

From the repository root:

.. code-block:: sh

   go build ./cmd/flowcollector

Run
---

Listen on UDP/2055 and write source endpoint device records to stdout:

.. code-block:: sh

   ./flowcollector -listen :2055

While testing, enable debug and status logs:

.. code-block:: sh

   ./flowcollector -listen :2055 -endpoint both -output flows.jsonl -debug -status 10s

Write both source and destination endpoint records to a JSONL file:

.. code-block:: sh

   ./flowcollector -listen :2055 -endpoint both -output flows.jsonl

The ``-endpoint`` option accepts ``src``, ``dst``, or ``both``.

RouterOS Export Check
---------------------

``/ip traffic-flow monitor`` shows the local RouterOS flow cache. It does not
prove that RouterOS is exporting UDP packets to the collector. Make sure a
target exists and uses NetFlow v5:

.. code-block:: text

   /ip traffic-flow set enabled=yes interfaces=all
   /ip traffic-flow target add address=<collector-ip> port=2055 version=5
   /ip traffic-flow target print detail

If ``-debug`` does not print ``rx ... version=5`` lines, the collector is not
receiving NetFlow v5 datagrams. Check the target address, firewall rules, route
to the collector, and that the collector is listening on the host address the
router can reach.

Output Shape
------------

Each line is a ``DeviceRecord``-shaped JSON object:

.. code-block:: json

   {
     "name": null,
     "host": "10.20.30.45",
     "mac": null,
     "serial": null,
     "vendor": null,
     "platform": null,
     "source": "netflow:v5",
     "identifiers": [],
     "metadata": {
       "exporter": "192.0.2.10",
       "direction": "src",
       "peer_host": "8.8.8.8",
       "src_host": "10.20.30.45",
       "dst_host": "8.8.8.8",
       "src_port": 54321,
       "dst_port": 53,
       "protocol": 17,
       "bytes": 12000,
       "packets": 40,
       "input_interface_index": 17,
       "output_interface_index": 3
     }
   }

Reconcile Collector Output
--------------------------

Because the collector emits ``DeviceRecord``-shaped rows, the client side stays
small. The loader classifies flow endpoints first, so public peers and exporters
do not pollute source-of-truth reconciliation:

.. code-block:: python

   from network_lang import (
       DeviceRecord,
       apply_flow_recon_policy,
       load_flow_devices,
       load_inventory,
       reconcile_devices,
   )

   inventory = load_inventory()
   expected = [
       DeviceRecord(
           name=record.get("name"),
           host=record["interfaces"][0]["ip_address"].split("/", 1)[0],
           source="inventory",
       )
       for record in inventory
       if "CPE-devices" in record.get("groups", [])
   ]
   infrastructure_hosts = [
       record["interfaces"][0]["ip_address"].split("/", 1)[0]
       for record in inventory
       if "CPE-devices" not in record.get("groups", [])
   ]
   observed = load_flow_devices(
       "flows.jsonl",
       scope="all",
       customer_hosts=[device.host for device in expected if device.host],
       known_infrastructure=infrastructure_hosts,
   )
   report = apply_flow_recon_policy(reconcile_devices(expected, observed))
   print(report.to_text())
   raise SystemExit(report.exit_code)

The report exits with status ``1`` when unknown internal hosts are present, and
``0`` when there are no unknown internal hosts.

That produces an operator-facing summary:

.. code-block:: text

   Unknown internal hosts observed: 0
   Matched customer endpoints: 1
   Infrastructure observed: 1
   External peers ignored: 9

   Matched customer endpoints:
   - 10.20.30.45 score=95 source=netflow:v5 exporter=192.0.2.10 interface=8

   Infrastructure observed:
   - 192.0.2.11 source=netflow:v5 exporter=192.0.2.10 interface=8

Known infrastructure can be tagged so it does not receive the
``unknown_internal`` flow class:

.. code-block:: python

   observed = load_flow_devices(
       "flows.jsonl",
       scope="internal",
       known_infrastructure=("192.0.2.11",),
   )

Endpoint Classification
-----------------------

Flow endpoints are classified before reconciliation:

.. code-block:: text

   public_external
   private_internal
   exporter
   known_infrastructure
   customer_endpoint
   unknown_internal
   ignored_peer

The default ``scope="internal"`` includes private/internal endpoints and
excludes public external peers, ignored peers, and exporters.

Use ``scope="external"`` when you want to inspect public peers separately:

.. code-block:: python

   external_peers = load_flow_devices("flows.jsonl", scope="external")

Set ``include_external_peers=True`` when you intentionally want public peers in
the same observed set as internal endpoints:

.. code-block:: python

   observed = load_flow_devices(
       "flows.jsonl",
       scope="internal",
       include_external_peers=True,
   )

Use ``scope="ignored"`` when you need to inspect broadcast, multicast,
link-local, or otherwise non-actionable endpoints:

.. code-block:: python

   ignored_peers = load_flow_devices("flows.jsonl", scope="ignored")

Policy Layer
------------

The default flow reconciliation policy maps classes to actions:

.. code-block:: python

   FLOW_RECON_POLICY = {
       "customer_endpoint": "match_or_score",
       "unknown_internal": "report",
       "private_internal": "report",
       "public_external": "ignore",
       "ignored_peer": "ignore",
       "exporter": "infrastructure",
       "known_infrastructure": "infrastructure",
   }

Pass a custom policy to ``apply_flow_recon_policy`` when a deployment wants to
promote or suppress a class differently.
