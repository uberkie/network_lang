Topology, Reconciliation, and Preflight
=======================================

Topology helpers answer a practical question before risky changes:

.. code-block:: text

   Does the operation target the interface we think it targets, and what live
   devices are currently observed there?

Device Records
--------------

:class:`network_lang.DeviceRecord` represents a device as seen in inventory,
RouterOS neighbor data, ARP tables, bridge host tables, or flow records.

.. code-block:: python

   from network_lang import DeviceRecord

   device = DeviceRecord(
       name="customer-cpe-01",
       host="10.20.30.45",
       mac="AA:BB:CC:DD:EE:01",
       identifiers=("radius:user/customer0172",),
   )

Matching uses normalized identity keys:

* ``name:<name>``
* ``host:<host>``
* ``mac:<mac>``
* ``serial:<serial>``
* any explicit ``identifiers``

MAC addresses are normalized across common separator styles. IP addresses are
normalized with Python's ``ipaddress`` module.

Device Reconciliation
---------------------

.. code-block:: python

   from network_lang import DeviceRecord, reconcile_devices

   expected = [
       DeviceRecord(name="edge-01", host="192.168.88.1"),
   ]

   observed = [
       DeviceRecord(name="edge-01-live", host="192.168.88.1"),
       DeviceRecord(name="unknown-cpe", host="10.20.30.45"),
   ]

   report = reconcile_devices(expected, observed)
   print(report.ok)
   print(report.matches)
   print(report.unknown_observed)
   print(report.missing_expected)

``report.ok`` is true when there are no unknown observed devices and no missing
expected devices.

Attachment Records
------------------

:class:`network_lang.AttachmentRecord` adds a network location to a
:class:`network_lang.DeviceRecord`.

.. code-block:: python

   from network_lang import AttachmentRecord, DeviceRecord

   attachment = AttachmentRecord(
       device=DeviceRecord(name="customer-cpe-01", mac="AA:BB:CC:DD:EE:01"),
       network_device="poe-switch-01",
       interface="ether2",
       source="inventory",
   )

Attachments match by device identity and compare by location:

.. code-block:: text

   network_device + interface + optional scope

This is how the library detects that a known device moved from one port to
another.

Attachment Reconciliation
-------------------------

.. code-block:: python

   from network_lang import AttachmentRecord, DeviceRecord, reconcile_attachments

   expected = [
       AttachmentRecord(
           DeviceRecord(name="cpe-01", mac="AA:BB:CC:DD:EE:01"),
           "poe-switch-01",
           "ether1",
       )
   ]

   observed = [
       AttachmentRecord(
           DeviceRecord(mac="AA-BB-CC-DD-EE-01"),
           "poe-switch-01",
           "ether4",
       )
   ]

   report = reconcile_attachments(expected, observed)
   print(report.moved)

The report contains matches, moved devices, unknown observations, missing
expected attachments, and duplicate observations.

Interface State Records
-----------------------

:class:`network_lang.InterfaceStateRecord` captures whether an interface
appears disabled, inactive, running, forwarding, or in another adapter-specific
status.

.. code-block:: python

   from network_lang import InterfaceStateRecord

   state = InterfaceStateRecord(
       network_device="poe-switch-01",
       interface="ether2",
       scope="bridge1",
       inactive=True,
       running=False,
       status="inactive",
   )

RouterOS bridge port rows can be normalized into interface states with
``routeros_bridge_ports_to_interface_states()``.

Preflight an Interface Operation
--------------------------------

``preflight_interface_operation()`` compares the operation target interface
against expected attachments, observed attachments, and optional interface
state.

.. code-block:: python

   from network_lang import (
       AttachmentRecord,
       DeviceRecord,
       InterfaceStateRecord,
       build_operation,
       preflight_interface_operation,
   )

   operation = build_operation(
       "network.interfaces.disable",
       target="poe-switch-01",
       name="ether1",
   )

   expected = [
       AttachmentRecord(
           DeviceRecord(name="cpe-01", mac="AA:BB:CC:DD:EE:01"),
           "poe-switch-01",
           "ether1",
       )
   ]

   observed = [
       AttachmentRecord(
           DeviceRecord(mac="AA-BB-CC-DD-EE-01"),
           "poe-switch-01",
           "ether4",
       )
   ]

   states = [
       InterfaceStateRecord(
           "poe-switch-01",
           "ether1",
           inactive=True,
           status="inactive",
       )
   ]

   report = preflight_interface_operation(operation, expected, observed, states)
   print(report.ok)
   print(report.risks)

Risks include expected devices observed on a different interface, unknown live
devices on the target interface, missing expected devices, duplicate observed
identity keys, and disabled, inactive, or non-running interface state.

Live RouterOS Preflight
-----------------------

With a resolved target, RouterOS topology collection and preflight can be
handled through :class:`network_lang.TargetDevice`.

.. code-block:: python

   from network_lang import target_device

   device = target_device("edge-01")
   result = device.preflight("network.interfaces.disable", name="ether2")

   if result.ok:
       print("preflight clear")
   else:
       print(result.error.code)
       print(result.data.risks)

Internally, this collects RouterOS neighbors and bridge ports, normalizes them,
and then runs the same preflight logic.

Flow Observations
-----------------

:class:`network_lang.FlowObservation` can turn passive flow samples into device
or attachment evidence.

.. code-block:: python

   from network_lang import (
       FlowObservation,
       flow_observations_to_attachments,
       resolve_flow_target,
   )

   flows = [
       FlowObservation(
           exporter="tower-nas-03",
           src_host="10.20.30.45",
           dst_host="8.8.8.8",
           ingress_interface="pppoe-customer0172",
           egress_interface="uplink-core",
           protocol="udp",
           dst_port=53,
           bytes=12000,
           packets=40,
           src_identifiers=("radius:user/customer0172",),
       )
   ]

   attachments = flow_observations_to_attachments(flows)
   target = resolve_flow_target("ip:10.20.30.45", flows)

``resolve_flow_target()`` returns the best matching observation with network
device, interface, direction, and confidence.
