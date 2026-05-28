Adapters
========

Adapters translate the neutral :class:`network_lang.Operation` model into
vendor-specific calls, plans, and normalized results.

RouterOS REST
-------------

The RouterOS adapter can plan and execute selected MikroTik RouterOS REST
operations.

.. code-block:: python

   from network_lang import build_operation
   from network_lang.adapters import RouterOSExecutor, RouterOSRestTransport
   from network_lang.adapters.ros import Ros

   operation = build_operation("network.system.identity.get", target="edge-01")

   ros = Ros("https://192.168.88.1/", "admin", "password", secure=False)
   transport = RouterOSRestTransport(ros)
   result = RouterOSExecutor(transport).execute(operation)

Supported RouterOS Mappings
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Operation
     - RouterOS REST path
     - Behavior
   * - ``network.system.identity.get``
     - ``/system/identity``
     - ``GET``
   * - ``network.neighbors.list``
     - ``/ip/neighbor``
     - ``GET`` with optional ``match`` filters
   * - ``network.bridge.hosts.list``
     - ``/interface/bridge/host``
     - ``GET`` with optional ``match`` filters
   * - ``network.bridge.ports.list``
     - ``/interface/bridge/port``
     - ``GET`` with optional ``match`` filters
   * - ``network.bridge.ports.create``
     - ``/interface/bridge/port``
     - ``PUT`` with ``port`` or ``data`` body
   * - ``network.interfaces.list``
     - ``/interface``
     - ``GET`` with optional ``match`` filters
   * - ``network.interfaces.get``
     - ``/interface``
     - ``GET``, adding ``name`` as a filter when supplied
   * - ``network.interfaces.disable``
     - ``/interface``
     - ``PATCH`` by ``id``, or lookup by ``name``/``match`` then patch
   * - ``network.interfaces.enable``
     - ``/interface``
     - ``PATCH`` by ``id``, or lookup by ``name``/``match`` then patch
   * - ``network.interfaces.<endpoint>.list``
     - ``/interface/<endpoint>``
     - Generic ``GET`` support for RouterOS interface submenus
   * - ``network.interfaces.<endpoint>.create``
     - ``/interface/<endpoint>``
     - Generic ``PUT`` with ``data``, ``interface``, or endpoint-named body
   * - ``network.interfaces.<endpoint>.update``
     - ``/interface/<endpoint>``
     - Generic ``PATCH`` by ``id``, or lookup by ``name``/``match`` then patch
   * - ``network.interfaces.<endpoint>.delete``
     - ``/interface/<endpoint>``
     - Generic ``DELETE`` by ``id``, or lookup by ``name``/``match`` then delete
   * - ``network.interfaces.<endpoint>.enable``, ``network.interfaces.<endpoint>.disable``
     - ``/interface/<endpoint>``
     - Generic ``PATCH`` of ``disabled`` by ``id``, or lookup then patch
   * - ``network.ip.<endpoint>.list``
     - ``/ip/<endpoint>``
     - Generic ``GET`` support for RouterOS IP submenus
   * - ``network.ip.<endpoint>.create``
     - ``/ip/<endpoint>``
     - Generic ``PUT`` with ``data``, ``ip``, or endpoint-named body
   * - ``network.ip.<endpoint>.update``
     - ``/ip/<endpoint>``
     - Generic ``PATCH`` by ``id``, or lookup by ``name``/``match`` then patch
   * - ``network.ip.<endpoint>.delete``
     - ``/ip/<endpoint>``
     - Generic ``DELETE`` by ``id``, or lookup by ``name``/``match`` then delete
   * - ``network.ip.<endpoint>.enable``, ``network.ip.<endpoint>.disable``
     - ``/ip/<endpoint>``
     - Generic ``PATCH`` of ``disabled`` by ``id``, or lookup then patch
   * - ``network.routing.<endpoint>.list``
     - ``/routing/<endpoint>``
     - Generic ``GET`` support for RouterOS routing submenus
   * - ``network.routing.<endpoint>.create``
     - ``/routing/<endpoint>``
     - Generic ``PUT`` with ``data``, ``routing``, or endpoint-named body
   * - ``network.routing.<endpoint>.update``
     - ``/routing/<endpoint>``
     - Generic ``PATCH`` by ``id``, or lookup by ``name``/``match`` then patch
   * - ``network.routing.<endpoint>.delete``
     - ``/routing/<endpoint>``
     - Generic ``DELETE`` by ``id``, or lookup by ``name``/``match`` then delete
   * - ``network.routing.<endpoint>.enable``, ``network.routing.<endpoint>.disable``
     - ``/routing/<endpoint>``
     - Generic ``PATCH`` of ``disabled`` by ``id``, or lookup then patch
   * - ``network.radius.list``
     - ``/radius``
     - Generic ``GET`` support for RouterOS RADIUS servers
   * - ``network.radius.create``
     - ``/radius``
     - Generic ``PUT`` with ``data`` or ``radius`` body
   * - ``network.radius.update``
     - ``/radius``
     - Generic ``PATCH`` by ``id``, or lookup by ``name``/``match`` then patch
   * - ``network.radius.delete``
     - ``/radius``
     - Generic ``DELETE`` by ``id``, or lookup by ``name``/``match`` then delete
   * - ``network.radius.enable``, ``network.radius.disable``
     - ``/radius``
     - Generic ``PATCH`` of ``disabled`` by ``id``, or lookup then patch
   * - ``network.radius.incoming.<action>``
     - ``/radius/incoming``
     - Generic ``list/get/create/update/delete/enable/disable`` support
   * - ``network.ppp.<endpoint>.list``
     - ``/ppp/<endpoint>``
     - Generic ``GET`` support for RouterOS PPP submenus
   * - ``network.ppp.<endpoint>.create``
     - ``/ppp/<endpoint>``
     - Generic ``PUT`` with ``data``, ``ppp``, or endpoint-named body
   * - ``network.ppp.<endpoint>.update``
     - ``/ppp/<endpoint>``
     - Generic ``PATCH`` by ``id``, or lookup by ``name``/``match`` then patch
   * - ``network.ppp.<endpoint>.delete``
     - ``/ppp/<endpoint>``
     - Generic ``DELETE`` by ``id``, or lookup by ``name``/``match`` then delete
   * - ``network.ppp.<endpoint>.enable``, ``network.ppp.<endpoint>.disable``
     - ``/ppp/<endpoint>``
     - Generic ``PATCH`` of ``disabled`` by ``id``, or lookup then patch
   * - ``network.routes.list``
     - ``/ip/route``
     - ``GET`` with optional ``match`` filters
   * - ``network.routes.create``
     - ``/ip/route``
     - ``PUT`` with ``route`` or ``data`` body
   * - ``network.firewall.rules.list``
     - ``/ip/firewall/filter``
     - ``GET`` with optional ``match`` filters
   * - ``network.firewall.rules.create``
     - ``/ip/firewall/filter``
     - ``PUT`` with ``rule`` or ``data`` body
   * - ``network.addresses.list``
     - ``/ip/address``
     - ``GET`` with optional ``match`` filters
   * - ``network.addresses.create``
     - ``/ip/address``
     - ``PUT`` with ``address`` or ``data`` body
   * - ``network.vlans.create``
     - ``/interface/vlan``
     - ``PUT`` with ``vlan`` or ``data`` body
   * - ``network.vlans.update``
     - ``/interface/vlan``
     - ``PATCH`` by ``id``, or lookup by ``name``/``match`` then patch
   * - ``network.wireless.clients.list``
     - ``/interface/wireless/registration-table``
     - ``GET`` with optional ``match`` filters

RouterOS Interface Endpoint Names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

RouterOS interface submenus are available under ``network.interfaces``.
Hyphenated RouterOS names use underscores in operation names. ``6to4`` is
``six_to_four`` because operation segments cannot start with a number.
The RouterOS ``/interface/list`` submenu is exposed as ``lists`` or
``interface_lists`` to avoid colliding with the ``list`` action.

.. code-block:: python

   build_operation("network.interfaces.ethernet.list", target="edge-01")
   build_operation(
       "network.interfaces.pppoe_client.create",
       target="edge-01",
       data={"name": "pppoe-out1", "interface": "ether1"},
   )
   build_operation(
       "network.interfaces.wireguard.disable",
       target="edge-01",
       name="wg-customers",
   )
   build_operation(
       "network.interfaces.ethernet.reset_counters.run",
       target="edge-01",
       name="ether1",
   )

The first interface pass maps these submenus:

.. code-block:: text

   six_to_four        macsec           vxlan
   bonding            macvlan          wifi
   bridge             mesh             wireguard
   detect_internet    ovpn_client      wireless
   dot1x              ovpn_server
   eoip               ppp_client
   eoipv6             ppp_server
   ethernet           pppoe_client
   gre                pppoe_server
   gre6               pptp_client
   ipip               pptp_server
   ipipv6             sstp_client
   l2tp_client        sstp_server
   l2tp_ether         veth
   l2tp_server        vlan
   lists              vpls
   lte                vrrp

RouterOS interface commands are represented with the existing ``run`` action:

.. code-block:: text

   network.interfaces.blink.run
   network.interfaces.comment.run
   network.interfaces.edit.run
   network.interfaces.export.run
   network.interfaces.find.run
   network.interfaces.monitor_traffic.run
   network.interfaces.print.run
   network.interfaces.reset.run
   network.interfaces.reset_counters.run
   network.interfaces.set.run

Commands can also be scoped below a submenu when RouterOS exposes that command
there, for example ``network.interfaces.ethernet.reset_counters.run``.

RouterOS IP Endpoint Names
~~~~~~~~~~~~~~~~~~~~~~~~~~

RouterOS ``/ip`` submenus are available under ``network.ip``. Hyphenated
RouterOS names use underscores in operation names.

.. code-block:: python

   build_operation("network.ip.address.list", target="edge-01")
   build_operation(
       "network.ip.dhcp_client.create",
       target="edge-01",
       data={"interface": "ether1", "add_default_route": True},
   )
   build_operation("network.ip.service.disable", target="edge-01", name="www")
   build_operation("network.ip.export.run", target="edge-01", file="ip-export")

The first IP pass maps these submenus:

.. code-block:: text

   address         firewall        packing      socks
   arp             hotspot         pool         ssh
   cloud           ipsec           proxy        tftp
   dhcp_client     kid_control     route        traffic_flow
   dhcp_relay      media           service      upnp
   dhcp_server     nat_pmp         settings     vrf
   dns             neighbor        smb

RouterOS ``/ip export`` is represented with the existing ``run`` action:

.. code-block:: text

   network.ip.export.run

RouterOS Routing Endpoint Names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

RouterOS ``/routing`` submenus are available under ``network.routing``.
Hyphenated RouterOS names use underscores in operation names.

.. code-block:: python

   build_operation("network.routing.table.list", target="edge-01")
   build_operation(
       "network.routing.bgp.create",
       target="edge-01",
       data={"name": "peer1", "remote_address": "192.0.2.1"},
   )
   build_operation("network.routing.ospf.disable", target="edge-01", name="ospf1")
   build_operation("network.routing.reinstall_fib.run", target="edge-01")

The first routing pass maps these submenus:

.. code-block:: text

   bfd         igmp_proxy     route
   bgp         isis           rpki
   fantasy     nexthop        rule
   filter      ospf           settings
   gmp         pimsm          stats
   id          rip            table

RouterOS routing commands are represented with the existing ``run`` action:

.. code-block:: text

   network.routing.discourse.run
   network.routing.export.run
   network.routing.reinstall_fib.run

RouterOS Radius Endpoint Names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

RouterOS ``/radius`` is available as ``network.radius``. The
``/radius/incoming`` submenu is available as ``network.radius.incoming``.

.. code-block:: python

   build_operation(
       "network.radius.create",
       target="edge-01",
       radius={
           "service": "ppp",
           "address": "192.0.2.10",
           "secret": "shared-secret",
           "authentication_port": 1812,
           "accounting_port": 1813,
       },
   )
   build_operation("network.radius.disable", target="edge-01", id="*2")
   build_operation("network.radius.incoming.update", target="edge-01", id="*1", incoming={"accept": True})
   build_operation("network.radius.export.run", target="edge-01")

The first radius pass maps these endpoint resources:

.. code-block:: text

   network.radius
   network.radius.incoming

RouterOS radius commands are represented with the existing ``run`` action:

.. code-block:: text

   network.radius.add.run
   network.radius.comment.run
   network.radius.disable.run
   network.radius.edit.run
   network.radius.enable.run
   network.radius.export.run
   network.radius.find.run
   network.radius.monitor.run
   network.radius.move.run
   network.radius.print.run
   network.radius.remove.run
   network.radius.reset.run
   network.radius.reset_counters.run
   network.radius.set.run

Commands can also be scoped below ``incoming`` when RouterOS exposes that
command there, for example ``network.radius.incoming.print.run``.

RouterOS PPP Endpoint Names
~~~~~~~~~~~~~~~~~~~~~~~~~~~

RouterOS ``/ppp`` submenus are available under ``network.ppp``. Hyphenated
RouterOS names use underscores in operation names, so ``/ppp/l2tp-secret`` is
``network.ppp.l2tp_secret``.

.. code-block:: python

   build_operation("network.ppp.active.list", target="edge-01")
   build_operation(
       "network.ppp.secret.create",
       target="edge-01",
       ppp={
           "name": "customer0172",
           "password": "shared-secret",
           "service": "pppoe",
           "profile": "customers",
           "local_address": "10.0.0.1",
           "remote_address": "10.0.0.172",
       },
   )
   build_operation(
       "network.ppp.profile.update",
       target="edge-01",
       name="customers",
       profile={"rate_limit": "20M/20M"},
   )
   build_operation("network.ppp.export.run", target="edge-01")

The first PPP pass maps these submenus:

.. code-block:: text

   aaa
   active
   l2tp_secret
   profile
   secret

RouterOS ``/ppp export`` is represented with the existing ``run`` action:

.. code-block:: text

   network.ppp.export.run

Commands can also be scoped below a submenu when RouterOS exposes that command
there, for example ``network.ppp.secret.export.run``.

Unsupported operations return an :class:`network_lang.OperationResult` with
``ok=False``, ``capability="unsupported"``, and
``error.code="UNSUPPORTED_OPERATION"``.

Planning Without Execution
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from network_lang import build_operation
   from network_lang.adapters import plan_routeros_operation

   operation = build_operation("network.interfaces.disable", target="edge-01", name="ether2")
   plan = plan_routeros_operation(operation)

   print(plan.capability)
   print(plan.warnings)

Disabling or enabling by ``id`` is a direct patch:

.. code-block:: python

   build_operation("network.interfaces.disable", target="edge-01", id="*2")

Disabling or enabling by ``name`` or ``match`` requires a read-before-write
lookup:

.. code-block:: python

   build_operation("network.interfaces.disable", target="edge-01", name="ether2")
   build_operation(
       "network.interfaces.disable",
       target="edge-01",
       match={"name": "ether2"},
   )

That plan has capability ``supported_via_fallback`` and includes a warning.

Key Translation
~~~~~~~~~~~~~~~

For common RouterOS resources, neutral snake-case keys are translated to
RouterOS REST keys. Unknown keys are converted from underscores to hyphens.

.. list-table::
   :header-rows: 1

   * - Neutral key
     - RouterOS key
   * - ``dst``, ``dst_address``
     - ``dst-address``
   * - ``table``, ``routing_table``
     - ``routing-table``
   * - ``pref_src``
     - ``pref-src``
   * - ``check_gateway``
     - ``check-gateway``
   * - ``src``, ``src_address``
     - ``src-address``
   * - ``src_port``
     - ``src-port``
   * - ``dst_port``
     - ``dst-port``
   * - ``in_interface``
     - ``in-interface``
   * - ``out_interface``
     - ``out-interface``
   * - ``connection_state``
     - ``connection-state``
   * - ``authentication_port``, ``accounting_port``
     - ``authentication-port``, ``accounting-port``
   * - ``local_address``, ``remote_address``
     - ``local-address``, ``remote-address``
   * - ``rate_limit``, ``use_encryption``
     - ``rate-limit``, ``use-encryption``

Normalizers
~~~~~~~~~~~

RouterOS observation rows can be converted into common records:

.. list-table::
   :header-rows: 1

   * - Function
     - Output
   * - ``routeros_neighbors_to_devices()``
     - :class:`network_lang.DeviceRecord` tuple
   * - ``routeros_neighbors_to_attachments()``
     - :class:`network_lang.AttachmentRecord` tuple
   * - ``routeros_arp_to_devices()``
     - :class:`network_lang.DeviceRecord` tuple
   * - ``routeros_arp_to_attachments()``
     - :class:`network_lang.AttachmentRecord` tuple
   * - ``routeros_bridge_hosts_to_attachments()``
     - :class:`network_lang.AttachmentRecord` tuple
   * - ``routeros_bridge_ports_to_interface_states()``
     - :class:`network_lang.InterfaceStateRecord` tuple

RouterOS Topology Composition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``collect_routeros_topology()`` composes two read operations:

.. code-block:: text

   network.neighbors.list
   network.bridge.ports.list

It returns a ``RouterOSTopologySnapshot`` containing normalized attachments,
normalized interface states, raw neighbor data, and raw bridge port data.

``preflight_routeros_operation()`` uses that snapshot to preflight risky
interface operations.

UNMS/UISP Controller REST
-------------------------

The UNMS/UISP adapter can execute controller API calls with token
authentication. It follows the legacy UNMS plugin convention of sending
``x-auth-token`` to ``/api/v2.1/``, and ``UNMSEndpoints.from_url()`` rewrites
``/crm/`` URLs to ``/nms/``.

.. code-block:: python

   from network_lang import target_device

   controller = target_device("uisp")
   result = controller.execute(
       controller.operation(
           "network.controller.devices.list",
           match={"site_id": "site-1"},
       )
   )

Inventory records need a controller URL and token:

.. code-block:: json

   {
       "name": "uisp",
       "url": "https://uisp.example.com/nms/",
       "vendor": "ubnt",
       "platform": "unms",
       "transport": "rest",
       "token": "change-me",
       "secure": false
   }

Supported Controller Mappings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Operation shape
     - API behavior
   * - ``network.controller.<resource>.list``
     - ``GET /<resource>`` with optional ``match``/``query`` params
   * - ``network.controller.<resource>.get``
     - ``GET /<resource>/<id>`` or filtered ``GET /<resource>``
   * - ``network.controller.<resource>.create``
     - ``POST /<resource>`` with ``data`` body
   * - ``network.controller.<resource>.update``
     - ``PATCH /<resource>/<id>`` with ``data`` body
   * - ``network.controller.<resource>.delete``
     - ``DELETE /<resource>/<id>`` with destructive warning
   * - ``network.unms.list(endpoint="devices/firmwares")``
     - ``GET /devices/firmwares``

Underscores in operation path segments and parameter keys are converted to
hyphens for controller paths and query/body keys.

Ubiquiti airOS Plans
--------------------

The airOS adapter currently plans endpoint calls. It does not execute HTTP
requests yet.

.. code-block:: python

   from network_lang import build_operation
   from network_lang.adapters import AirOSEndpoints, plan_airos_operation

   endpoints = AirOSEndpoints.from_host("192.168.0.20")
   operation = build_operation("network.wireless.clients.list", target="cpe-01")
   plan = plan_airos_operation(operation, endpoints)

Supported airOS Plans
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Operation
     - Endpoint behavior
   * - ``network.system.identity.get``
     - Login, then ``GET /status.cgi``
   * - ``network.system.status.get``
     - Login, then ``GET /status.cgi``
   * - ``network.wireless.clients.list``
     - Login, then ``GET /status.cgi``
   * - ``network.system.warnings.get``
     - Login, then ``GET /api/warnings``, then logout
   * - ``network.system.reboot.run``
     - Login, then ``POST /reboot.cgi``
   * - ``network.wireless.clients.delete``
     - Login, then ``POST /stakick.cgi`` with ``match.mac``
   * - ``network.system.provisioning.update``
     - Login, then ``POST /api/provmode`` with ``data.enabled``
   * - ``network.firmware.update.get``
     - Login, then ``GET /api/fw/update-check``
   * - ``network.firmware.download.run``
     - Login, then ``POST /api/fw/download``
   * - ``network.firmware.download_progress.get``
     - Login, then ``GET /api/fw/download-progress``
   * - ``network.firmware.install.run``
     - Login, then ``POST /fwflash.cgi``

Firmware major version ``6`` marks status reads as ``supported_via_fallback``
because airOS 6 uses the legacy login path. Operations that interrupt service,
such as reboot and firmware install, include warnings in the returned plan.
