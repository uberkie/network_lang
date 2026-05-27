import unittest

from network_lang import build_operation
from network_lang import AttachmentRecord, DeviceRecord, preflight_interface_operation
from network_lang.adapters import (
    RouterOSExecutor,
    RouterOSRestTransport,
    collect_routeros_topology,
    plan_routeros_operation,
    preflight_routeros_operation,
    routeros_arp_to_attachments,
    routeros_arp_to_devices,
    routeros_bridge_hosts_to_attachments,
    routeros_bridge_ports_to_interface_states,
    routeros_neighbors_to_attachments,
    routeros_neighbors_to_devices,
)


class FakeRouterOSTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, path, params=None, body=None):
        self.requests.append(
            {
                "method": method,
                "path": path,
                "params": params,
                "body": body,
            }
        )
        if not self.responses:
            return None
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.raised = False

    def raise_for_status(self):
        self.raised = True


class FakeRosSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params=None, verify=None):
        self.calls.append(("GET", url, params, None, verify))
        return self.response

    def put(self, url, json=None):
        self.calls.append(("PUT", url, None, json, None))
        return self.response

    def patch(self, url, json=None):
        self.calls.append(("PATCH", url, None, json, None))
        return self.response

    def post(self, url, json=None):
        self.calls.append(("POST", url, None, json, None))
        return self.response

    def delete(self, url):
        self.calls.append(("DELETE", url, None, None, None))
        return self.response


class FakeRos:
    def __init__(self, response):
        self.url = "https://router.example/rest"
        self.secure = False
        self.session = FakeRosSession(response)


class RouterOSPlanTests(unittest.TestCase):
    def test_identity_get_maps_to_rest_path(self):
        operation = build_operation("network.system.identity.get", target="router-01")

        plan = plan_routeros_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.capability, "supported")
        self.assertEqual(plan.steps[0].method, "GET")
        self.assertEqual(plan.steps[0].path, "/system/identity")

    def test_neighbors_list_maps_to_rest_path(self):
        operation = build_operation("network.neighbors.list", target="router-01")

        plan = plan_routeros_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.capability, "supported")
        self.assertEqual(plan.steps[0].method, "GET")
        self.assertEqual(plan.steps[0].path, "/ip/neighbor")

    def test_bridge_hosts_list_maps_to_rest_path(self):
        operation = build_operation("network.bridge.hosts.list", target="router-01")

        plan = plan_routeros_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.steps[0].method, "GET")
        self.assertEqual(plan.steps[0].path, "/interface/bridge/host")

    def test_bridge_ports_list_maps_to_rest_path(self):
        operation = build_operation("network.bridge.ports.list", target="router-01")

        plan = plan_routeros_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.steps[0].method, "GET")
        self.assertEqual(plan.steps[0].path, "/interface/bridge/port")

    def test_bridge_port_create_maps_to_rest_path(self):
        operation = build_operation(
            "network.bridge.ports.create",
            target="router-01",
            port={
                "bridge": "bridge2",
                "interface": "ether8",
                "pvid": 20,
                "ingress_filtering": True,
            },
        )

        plan = plan_routeros_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.steps[0].method, "PUT")
        self.assertEqual(plan.steps[0].path, "/interface/bridge/port")
        self.assertEqual(
            plan.steps[0].body,
            {
                "bridge": "bridge2",
                "interface": "ether8",
                "pvid": 20,
                "ingress-filtering": True,
            },
        )

    def test_route_create_translates_neutral_keys(self):
        operation = build_operation(
            "network.routes.create",
            target="router-01",
            route={
                "dst": "0.0.0.0/0",
                "gateway": "192.168.88.1",
                "table": "main",
            },
        )

        plan = plan_routeros_operation(operation)

        self.assertEqual(plan.steps[0].method, "PUT")
        self.assertEqual(plan.steps[0].path, "/ip/route")
        self.assertEqual(
            plan.steps[0].body,
            {
                "dst-address": "0.0.0.0/0",
                "gateway": "192.168.88.1",
                "routing-table": "main",
            },
        )

    def test_firewall_rule_create_translates_common_keys(self):
        operation = build_operation(
            "network.firewall.rules.create",
            target="router-01",
            rule={
                "chain": "forward",
                "action": "drop",
                "src": "10.20.30.0/24",
                "dst": "0.0.0.0/0",
            },
        )

        plan = plan_routeros_operation(operation)

        self.assertEqual(plan.steps[0].path, "/ip/firewall/filter")
        self.assertEqual(
            plan.steps[0].body,
            {
                "chain": "forward",
                "action": "drop",
                "src-address": "10.20.30.0/24",
                "dst-address": "0.0.0.0/0",
            },
        )

    def test_interface_disable_by_name_requires_lookup(self):
        operation = build_operation(
            "network.interfaces.disable",
            target="router-01",
            name="ether1",
        )

        plan = plan_routeros_operation(operation)

        self.assertEqual(plan.capability, "supported_via_fallback")
        self.assertEqual([step.method for step in plan.steps], ["GET", "PATCH"])
        self.assertEqual(plan.steps[0].params, {"name": "ether1"})
        self.assertEqual(plan.steps[1].body, {"disabled": True})

    def test_interface_enable_by_id_patches_directly(self):
        operation = build_operation(
            "network.interfaces.enable",
            target="router-01",
            id="*1",
        )

        plan = plan_routeros_operation(operation)

        self.assertEqual(plan.capability, "supported")
        self.assertEqual(plan.steps[0].method, "PATCH")
        self.assertEqual(plan.steps[0].path, "/interface/*1")
        self.assertEqual(plan.steps[0].body, {"disabled": False})

    def test_interface_endpoint_family_maps_to_rest_paths(self):
        endpoints = {
            "six_to_four": "/interface/6to4",
            "bonding": "/interface/bonding",
            "bridge": "/interface/bridge",
            "detect_internet": "/interface/detect-internet",
            "dot1x": "/interface/dot1x",
            "eoip": "/interface/eoip",
            "eoipv6": "/interface/eoipv6",
            "ethernet": "/interface/ethernet",
            "gre": "/interface/gre",
            "gre6": "/interface/gre6",
            "ipip": "/interface/ipip",
            "ipipv6": "/interface/ipipv6",
            "l2tp_client": "/interface/l2tp-client",
            "l2tp_ether": "/interface/l2tp-ether",
            "l2tp_server": "/interface/l2tp-server",
            "lists": "/interface/list",
            "lte": "/interface/lte",
            "macsec": "/interface/macsec",
            "macvlan": "/interface/macvlan",
            "mesh": "/interface/mesh",
            "ovpn_client": "/interface/ovpn-client",
            "ovpn_server": "/interface/ovpn-server",
            "ppp_client": "/interface/ppp-client",
            "ppp_server": "/interface/ppp-server",
            "pppoe_client": "/interface/pppoe-client",
            "pppoe_server": "/interface/pppoe-server",
            "pptp_client": "/interface/pptp-client",
            "pptp_server": "/interface/pptp-server",
            "sstp_client": "/interface/sstp-client",
            "sstp_server": "/interface/sstp-server",
            "veth": "/interface/veth",
            "vlan": "/interface/vlan",
            "vpls": "/interface/vpls",
            "vrrp": "/interface/vrrp",
            "vxlan": "/interface/vxlan",
            "wifi": "/interface/wifi",
            "wireguard": "/interface/wireguard",
            "wireless": "/interface/wireless",
        }

        for operation_segment, path in endpoints.items():
            with self.subTest(operation_segment=operation_segment):
                operation = build_operation(
                    f"network.interfaces.{operation_segment}.list",
                    target="router-01",
                )

                plan = plan_routeros_operation(operation)

                self.assertTrue(plan.supported)
                self.assertEqual(plan.steps[0].method, "GET")
                self.assertEqual(plan.steps[0].path, path)

    def test_interface_endpoint_create_update_delete_and_toggle_are_generic(self):
        create = plan_routeros_operation(
            build_operation(
                "network.interfaces.vxlan.create",
                target="router-01",
                data={"name": "vxlan10", "vni": 10, "allow_fast_path": True},
            )
        )
        update = plan_routeros_operation(
            build_operation(
                "network.interfaces.ethernet.update",
                target="router-01",
                name="ether1",
                data={"comment": "uplink", "auto_negotiation": False},
            )
        )
        delete = plan_routeros_operation(
            build_operation(
                "network.interfaces.macvlan.delete",
                target="router-01",
                name="macvlan-temp",
            )
        )
        disable = plan_routeros_operation(
            build_operation(
                "network.interfaces.wireguard.disable",
                target="router-01",
                id="*7",
            )
        )

        self.assertEqual(create.steps[0].method, "PUT")
        self.assertEqual(create.steps[0].path, "/interface/vxlan")
        self.assertEqual(
            create.steps[0].body,
            {"name": "vxlan10", "vni": 10, "allow-fast-path": True},
        )
        self.assertEqual(update.capability, "supported_via_fallback")
        self.assertEqual(update.steps[0].path, "/interface/ethernet")
        self.assertEqual(update.steps[0].params, {"name": "ether1"})
        self.assertEqual(
            update.steps[1].body,
            {"comment": "uplink", "auto-negotiation": False},
        )
        self.assertEqual(delete.capability, "supported_via_fallback")
        self.assertEqual([step.method for step in delete.steps], ["GET", "DELETE"])
        self.assertEqual(delete.steps[0].path, "/interface/macvlan")
        self.assertEqual(delete.steps[1].path, "/interface/macvlan/<resolved-id>")
        self.assertEqual(disable.capability, "supported")
        self.assertEqual(disable.steps[0].method, "PATCH")
        self.assertEqual(disable.steps[0].path, "/interface/wireguard/*7")
        self.assertEqual(disable.steps[0].body, {"disabled": True})

    def test_interface_command_run_maps_to_post_path(self):
        operations = {
            "network.interfaces.blink.run": "/interface/blink",
            "network.interfaces.comment.run": "/interface/comment",
            "network.interfaces.edit.run": "/interface/edit",
            "network.interfaces.export.run": "/interface/export",
            "network.interfaces.find.run": "/interface/find",
            "network.interfaces.monitor_traffic.run": "/interface/monitor-traffic",
            "network.interfaces.print.run": "/interface/print",
            "network.interfaces.reset.run": "/interface/reset",
            "network.interfaces.reset_counters.run": "/interface/reset-counters",
            "network.interfaces.set.run": "/interface/set",
            "network.interfaces.ethernet.reset_counters.run": (
                "/interface/ethernet/reset-counters"
            ),
        }

        for operation_name, path in operations.items():
            with self.subTest(operation_name=operation_name):
                operation = build_operation(
                    operation_name,
                    target="router-01",
                    name="ether1",
                )

                plan = plan_routeros_operation(operation)

                self.assertTrue(plan.supported)
                self.assertEqual(plan.steps[0].method, "POST")
                self.assertEqual(plan.steps[0].path, path)
                self.assertEqual(plan.steps[0].body, {"name": "ether1"})

    def test_ip_endpoint_family_maps_to_rest_paths(self):
        endpoints = {
            "address": "/ip/address",
            "arp": "/ip/arp",
            "cloud": "/ip/cloud",
            "dhcp_client": "/ip/dhcp-client",
            "dhcp_relay": "/ip/dhcp-relay",
            "dhcp_server": "/ip/dhcp-server",
            "dns": "/ip/dns",
            "firewall": "/ip/firewall",
            "hotspot": "/ip/hotspot",
            "ipsec": "/ip/ipsec",
            "kid_control": "/ip/kid-control",
            "media": "/ip/media",
            "nat_pmp": "/ip/nat-pmp",
            "neighbor": "/ip/neighbor",
            "packing": "/ip/packing",
            "pool": "/ip/pool",
            "proxy": "/ip/proxy",
            "route": "/ip/route",
            "service": "/ip/service",
            "settings": "/ip/settings",
            "smb": "/ip/smb",
            "socks": "/ip/socks",
            "ssh": "/ip/ssh",
            "tftp": "/ip/tftp",
            "traffic_flow": "/ip/traffic-flow",
            "upnp": "/ip/upnp",
            "vrf": "/ip/vrf",
        }

        for operation_segment, path in endpoints.items():
            with self.subTest(operation_segment=operation_segment):
                operation = build_operation(
                    f"network.ip.{operation_segment}.list",
                    target="router-01",
                )

                plan = plan_routeros_operation(operation)

                self.assertTrue(plan.supported)
                self.assertEqual(plan.steps[0].method, "GET")
                self.assertEqual(plan.steps[0].path, path)

    def test_ip_endpoint_create_update_delete_and_toggle_are_generic(self):
        create = plan_routeros_operation(
            build_operation(
                "network.ip.dhcp_client.create",
                target="router-01",
                data={
                    "interface": "ether1",
                    "add_default_route": True,
                    "use_peer_dns": False,
                },
            )
        )
        update = plan_routeros_operation(
            build_operation(
                "network.ip.pool.update",
                target="router-01",
                name="customers",
                data={"ranges": "10.20.30.2-10.20.30.254"},
            )
        )
        delete = plan_routeros_operation(
            build_operation(
                "network.ip.hotspot.delete",
                target="router-01",
                name="hotspot1",
            )
        )
        disable = plan_routeros_operation(
            build_operation(
                "network.ip.service.disable",
                target="router-01",
                id="*2",
            )
        )

        self.assertEqual(create.steps[0].method, "PUT")
        self.assertEqual(create.steps[0].path, "/ip/dhcp-client")
        self.assertEqual(
            create.steps[0].body,
            {
                "interface": "ether1",
                "add-default-route": True,
                "use-peer-dns": False,
            },
        )
        self.assertEqual(update.capability, "supported_via_fallback")
        self.assertEqual(update.steps[0].path, "/ip/pool")
        self.assertEqual(update.steps[0].params, {"name": "customers"})
        self.assertEqual(
            update.steps[1].body,
            {"ranges": "10.20.30.2-10.20.30.254"},
        )
        self.assertEqual(delete.capability, "supported_via_fallback")
        self.assertEqual([step.method for step in delete.steps], ["GET", "DELETE"])
        self.assertEqual(delete.steps[0].path, "/ip/hotspot")
        self.assertEqual(delete.steps[1].path, "/ip/hotspot/<resolved-id>")
        self.assertEqual(disable.capability, "supported")
        self.assertEqual(disable.steps[0].method, "PATCH")
        self.assertEqual(disable.steps[0].path, "/ip/service/*2")
        self.assertEqual(disable.steps[0].body, {"disabled": True})

    def test_ip_export_command_run_maps_to_post_path(self):
        operation = build_operation(
            "network.ip.export.run",
            target="router-01",
            file="ip-export",
        )

        plan = plan_routeros_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.steps[0].method, "POST")
        self.assertEqual(plan.steps[0].path, "/ip/export")
        self.assertEqual(plan.steps[0].body, {"file": "ip-export"})

    def test_routing_endpoint_family_maps_to_rest_paths(self):
        endpoints = {
            "bfd": "/routing/bfd",
            "bgp": "/routing/bgp",
            "fantasy": "/routing/fantasy",
            "filter": "/routing/filter",
            "gmp": "/routing/gmp",
            "id": "/routing/id",
            "igmp_proxy": "/routing/igmp-proxy",
            "isis": "/routing/isis",
            "nexthop": "/routing/nexthop",
            "ospf": "/routing/ospf",
            "pimsm": "/routing/pimsm",
            "rip": "/routing/rip",
            "route": "/routing/route",
            "rpki": "/routing/rpki",
            "rule": "/routing/rule",
            "settings": "/routing/settings",
            "stats": "/routing/stats",
            "table": "/routing/table",
        }

        for operation_segment, path in endpoints.items():
            with self.subTest(operation_segment=operation_segment):
                operation = build_operation(
                    f"network.routing.{operation_segment}.list",
                    target="router-01",
                )

                plan = plan_routeros_operation(operation)

                self.assertTrue(plan.supported)
                self.assertEqual(plan.steps[0].method, "GET")
                self.assertEqual(plan.steps[0].path, path)

    def test_routing_endpoint_create_update_delete_and_toggle_are_generic(self):
        create = plan_routeros_operation(
            build_operation(
                "network.routing.bgp.create",
                target="router-01",
                data={
                    "name": "peer1",
                    "remote_address": "192.0.2.1",
                    "address_families": "ip",
                },
            )
        )
        update = plan_routeros_operation(
            build_operation(
                "network.routing.rule.update",
                target="router-01",
                name="prefer-main",
                data={"routing_table": "main", "disabled": False},
            )
        )
        delete = plan_routeros_operation(
            build_operation(
                "network.routing.table.delete",
                target="router-01",
                name="old-table",
            )
        )
        disable = plan_routeros_operation(
            build_operation(
                "network.routing.ospf.disable",
                target="router-01",
                id="*5",
            )
        )

        self.assertEqual(create.steps[0].method, "PUT")
        self.assertEqual(create.steps[0].path, "/routing/bgp")
        self.assertEqual(
            create.steps[0].body,
            {
                "name": "peer1",
                "remote-address": "192.0.2.1",
                "address-families": "ip",
            },
        )
        self.assertEqual(update.capability, "supported_via_fallback")
        self.assertEqual(update.steps[0].path, "/routing/rule")
        self.assertEqual(update.steps[0].params, {"name": "prefer-main"})
        self.assertEqual(
            update.steps[1].body,
            {"routing-table": "main", "disabled": False},
        )
        self.assertEqual(delete.capability, "supported_via_fallback")
        self.assertEqual([step.method for step in delete.steps], ["GET", "DELETE"])
        self.assertEqual(delete.steps[0].path, "/routing/table")
        self.assertEqual(delete.steps[1].path, "/routing/table/<resolved-id>")
        self.assertEqual(disable.capability, "supported")
        self.assertEqual(disable.steps[0].method, "PATCH")
        self.assertEqual(disable.steps[0].path, "/routing/ospf/*5")
        self.assertEqual(disable.steps[0].body, {"disabled": True})

    def test_routing_command_run_maps_to_post_path(self):
        operations = {
            "network.routing.discourse.run": "/routing/discourse",
            "network.routing.export.run": "/routing/export",
            "network.routing.reinstall_fib.run": "/routing/reinstall-fib",
        }

        for operation_name, path in operations.items():
            with self.subTest(operation_name=operation_name):
                operation = build_operation(
                    operation_name,
                    target="router-01",
                    file="routing-export",
                )

                plan = plan_routeros_operation(operation)

                self.assertTrue(plan.supported)
                self.assertEqual(plan.steps[0].method, "POST")
                self.assertEqual(plan.steps[0].path, path)
                self.assertEqual(plan.steps[0].body, {"file": "routing-export"})

    def test_radius_endpoint_family_maps_to_rest_paths(self):
        endpoints = {
            "": "/radius",
            "incoming": "/radius/incoming",
        }

        for operation_segment, path in endpoints.items():
            with self.subTest(operation_segment=operation_segment):
                operation_name = "network.radius.list"
                if operation_segment:
                    operation_name = f"network.radius.{operation_segment}.list"
                operation = build_operation(operation_name, target="router-01")

                plan = plan_routeros_operation(operation)

                self.assertTrue(plan.supported)
                self.assertEqual(plan.steps[0].method, "GET")
                self.assertEqual(plan.steps[0].path, path)

    def test_radius_endpoint_create_update_delete_and_toggle_are_generic(self):
        create = plan_routeros_operation(
            build_operation(
                "network.radius.create",
                target="router-01",
                data={
                    "service": "ppp",
                    "address": "192.0.2.10",
                    "secret": "testing",
                    "authentication_port": 1812,
                    "accounting_port": 1813,
                    "src_address": "192.0.2.1",
                },
            )
        )
        update = plan_routeros_operation(
            build_operation(
                "network.radius.incoming.update",
                target="router-01",
                id="*1",
                incoming={"accept": True, "port": 3799},
            )
        )
        delete = plan_routeros_operation(
            build_operation(
                "network.radius.delete",
                target="router-01",
                match={"address": "192.0.2.10", "service": "ppp"},
            )
        )
        disable = plan_routeros_operation(
            build_operation(
                "network.radius.disable",
                target="router-01",
                id="*2",
            )
        )

        self.assertEqual(create.steps[0].method, "PUT")
        self.assertEqual(create.steps[0].path, "/radius")
        self.assertEqual(
            create.steps[0].body,
            {
                "service": "ppp",
                "address": "192.0.2.10",
                "secret": "testing",
                "authentication-port": 1812,
                "accounting-port": 1813,
                "src-address": "192.0.2.1",
            },
        )
        self.assertEqual(update.capability, "supported")
        self.assertEqual(update.steps[0].method, "PATCH")
        self.assertEqual(update.steps[0].path, "/radius/incoming/*1")
        self.assertEqual(update.steps[0].body, {"accept": True, "port": 3799})
        self.assertEqual(delete.capability, "supported_via_fallback")
        self.assertEqual([step.method for step in delete.steps], ["GET", "DELETE"])
        self.assertEqual(delete.steps[0].path, "/radius")
        self.assertEqual(
            delete.steps[0].params,
            {"address": "192.0.2.10", "service": "ppp"},
        )
        self.assertEqual(delete.steps[1].path, "/radius/<resolved-id>")
        self.assertEqual(disable.capability, "supported")
        self.assertEqual(disable.steps[0].method, "PATCH")
        self.assertEqual(disable.steps[0].path, "/radius/*2")
        self.assertEqual(disable.steps[0].body, {"disabled": True})

    def test_radius_command_run_maps_to_post_path(self):
        operations = {
            "network.radius.add.run": "/radius/add",
            "network.radius.comment.run": "/radius/comment",
            "network.radius.disable.run": "/radius/disable",
            "network.radius.edit.run": "/radius/edit",
            "network.radius.enable.run": "/radius/enable",
            "network.radius.export.run": "/radius/export",
            "network.radius.find.run": "/radius/find",
            "network.radius.monitor.run": "/radius/monitor",
            "network.radius.move.run": "/radius/move",
            "network.radius.print.run": "/radius/print",
            "network.radius.remove.run": "/radius/remove",
            "network.radius.reset.run": "/radius/reset",
            "network.radius.reset_counters.run": "/radius/reset-counters",
            "network.radius.set.run": "/radius/set",
            "network.radius.incoming.print.run": "/radius/incoming/print",
            "network.radius.incoming.reset_counters.run": (
                "/radius/incoming/reset-counters"
            ),
        }

        for operation_name, path in operations.items():
            with self.subTest(operation_name=operation_name):
                operation = build_operation(
                    operation_name,
                    target="router-01",
                    id="*1",
                )

                plan = plan_routeros_operation(operation)

                self.assertTrue(plan.supported)
                self.assertEqual(plan.steps[0].method, "POST")
                self.assertEqual(plan.steps[0].path, path)
                self.assertEqual(plan.steps[0].body, {"id": "*1"})

    def test_ppp_endpoint_family_maps_to_rest_paths(self):
        endpoints = {
            "aaa": "/ppp/aaa",
            "active": "/ppp/active",
            "l2tp_secret": "/ppp/l2tp-secret",
            "profile": "/ppp/profile",
            "secret": "/ppp/secret",
        }

        for operation_segment, path in endpoints.items():
            with self.subTest(operation_segment=operation_segment):
                operation = build_operation(
                    f"network.ppp.{operation_segment}.list",
                    target="router-01",
                )

                plan = plan_routeros_operation(operation)

                self.assertTrue(plan.supported)
                self.assertEqual(plan.steps[0].method, "GET")
                self.assertEqual(plan.steps[0].path, path)

    def test_ppp_endpoint_create_update_delete_and_toggle_are_generic(self):
        create = plan_routeros_operation(
            build_operation(
                "network.ppp.secret.create",
                target="router-01",
                data={
                    "name": "customer0172",
                    "password": "testing",
                    "service": "pppoe",
                    "profile": "customers",
                    "local_address": "10.0.0.1",
                    "remote_address": "10.0.0.172",
                },
            )
        )
        update = plan_routeros_operation(
            build_operation(
                "network.ppp.profile.update",
                target="router-01",
                name="customers",
                profile={"rate_limit": "20M/20M", "use_encryption": "required"},
            )
        )
        delete = plan_routeros_operation(
            build_operation(
                "network.ppp.l2tp_secret.delete",
                target="router-01",
                name="legacy-tunnel",
            )
        )
        disable = plan_routeros_operation(
            build_operation(
                "network.ppp.secret.disable",
                target="router-01",
                id="*8",
            )
        )

        self.assertEqual(create.steps[0].method, "PUT")
        self.assertEqual(create.steps[0].path, "/ppp/secret")
        self.assertEqual(
            create.steps[0].body,
            {
                "name": "customer0172",
                "password": "testing",
                "service": "pppoe",
                "profile": "customers",
                "local-address": "10.0.0.1",
                "remote-address": "10.0.0.172",
            },
        )
        self.assertEqual(update.capability, "supported_via_fallback")
        self.assertEqual(update.steps[0].path, "/ppp/profile")
        self.assertEqual(update.steps[0].params, {"name": "customers"})
        self.assertEqual(
            update.steps[1].body,
            {"rate-limit": "20M/20M", "use-encryption": "required"},
        )
        self.assertEqual(delete.capability, "supported_via_fallback")
        self.assertEqual([step.method for step in delete.steps], ["GET", "DELETE"])
        self.assertEqual(delete.steps[0].path, "/ppp/l2tp-secret")
        self.assertEqual(delete.steps[1].path, "/ppp/l2tp-secret/<resolved-id>")
        self.assertEqual(disable.capability, "supported")
        self.assertEqual(disable.steps[0].method, "PATCH")
        self.assertEqual(disable.steps[0].path, "/ppp/secret/*8")
        self.assertEqual(disable.steps[0].body, {"disabled": True})

    def test_ppp_export_command_run_maps_to_post_path(self):
        operations = {
            "network.ppp.export.run": "/ppp/export",
            "network.ppp.secret.export.run": "/ppp/secret/export",
        }

        for operation_name, path in operations.items():
            with self.subTest(operation_name=operation_name):
                operation = build_operation(
                    operation_name,
                    target="router-01",
                    file="ppp-export",
                )

                plan = plan_routeros_operation(operation)

                self.assertTrue(plan.supported)
                self.assertEqual(plan.steps[0].method, "POST")
                self.assertEqual(plan.steps[0].path, path)
                self.assertEqual(plan.steps[0].body, {"file": "ppp-export"})

    def test_vlan_create_maps_to_rest_path(self):
        operation = build_operation(
            "network.vlans.create",
            target="router-01",
            vlan={
                "name": "vlan_mock_client",
                "interface": "bridge2",
                "vlan_id": 20,
            },
        )

        plan = plan_routeros_operation(operation)

        self.assertTrue(plan.supported)
        self.assertEqual(plan.steps[0].method, "PUT")
        self.assertEqual(plan.steps[0].path, "/interface/vlan")
        self.assertEqual(
            plan.steps[0].body,
            {
                "name": "vlan_mock_client",
                "interface": "bridge2",
                "vlan-id": 20,
            },
        )

    def test_vlan_update_by_id_patches_directly(self):
        operation = build_operation(
            "network.vlans.update",
            target="router-01",
            id="*4",
            vlan={"vlan_id": 30},
        )

        plan = plan_routeros_operation(operation)

        self.assertEqual(plan.capability, "supported")
        self.assertEqual(plan.steps[0].method, "PATCH")
        self.assertEqual(plan.steps[0].path, "/interface/vlan/*4")
        self.assertEqual(plan.steps[0].body, {"vlan-id": 30})

    def test_vlan_update_by_name_requires_lookup(self):
        operation = build_operation(
            "network.vlans.update",
            target="router-01",
            name="vlan_mock_client",
            vlan={"vlan_id": 30},
        )

        plan = plan_routeros_operation(operation)

        self.assertEqual(plan.capability, "supported_via_fallback")
        self.assertEqual([step.method for step in plan.steps], ["GET", "PATCH"])
        self.assertEqual(plan.steps[0].path, "/interface/vlan")
        self.assertEqual(plan.steps[0].params, {"name": "vlan_mock_client"})
        self.assertEqual(plan.steps[1].path, "/interface/vlan/<resolved-id>")
        self.assertEqual(plan.steps[1].body, {"vlan-id": 30})

    def test_unknown_operation_is_unsupported(self):
        operation = build_operation("network.system.reboot.run", target="router-01")

        plan = plan_routeros_operation(operation)

        self.assertFalse(plan.supported)
        self.assertEqual(plan.capability, "unsupported")


class RouterOSExecutorTests(unittest.TestCase):
    def test_executes_get_operation(self):
        operation = build_operation("network.system.identity.get", target="router-01")
        transport = FakeRouterOSTransport([{"name": "edge-01"}])

        result = RouterOSExecutor(transport).execute(operation)

        self.assertTrue(result.ok)
        self.assertEqual(result.operation, "network.system.identity.get")
        self.assertEqual(result.target, "router-01")
        self.assertEqual(result.adapter["vendor"], "mikrotik")
        self.assertEqual(result.data, {"name": "edge-01"})
        self.assertEqual(
            transport.requests,
            [
                {
                    "method": "GET",
                    "path": "/system/identity",
                    "params": None,
                    "body": None,
                }
            ],
        )

    def test_executes_route_create(self):
        operation = build_operation(
            "network.routes.create",
            target="router-01",
            route={"dst": "0.0.0.0/0", "gateway": "192.168.88.1"},
        )
        transport = FakeRouterOSTransport([{"id": "*1"}])

        result = RouterOSExecutor(transport).execute(operation)

        self.assertTrue(result.ok)
        self.assertEqual(result.data, {"id": "*1"})
        self.assertEqual(transport.requests[0]["method"], "PUT")
        self.assertEqual(transport.requests[0]["path"], "/ip/route")
        self.assertEqual(
            transport.requests[0]["body"],
            {"dst-address": "0.0.0.0/0", "gateway": "192.168.88.1"},
        )

    def test_resolves_id_before_interface_disable(self):
        operation = build_operation(
            "network.interfaces.disable",
            target="router-01",
            name="ether1",
        )
        transport = FakeRouterOSTransport(
            [
                [{"id": "*2", "name": "ether1"}],
                {"id": "*2", "disabled": True},
            ]
        )

        result = RouterOSExecutor(transport).execute(operation)

        self.assertTrue(result.ok)
        self.assertEqual(result.data, {"id": "*2", "disabled": True})
        self.assertEqual(
            transport.requests,
            [
                {
                    "method": "GET",
                    "path": "/interface",
                    "params": {"name": "ether1"},
                    "body": None,
                },
                {
                    "method": "PATCH",
                    "path": "/interface/*2",
                    "params": None,
                    "body": {"disabled": True},
                },
            ],
        )

    def test_lookup_not_found_returns_error_result(self):
        operation = build_operation(
            "network.interfaces.disable",
            target="router-01",
            name="ether99",
        )
        transport = FakeRouterOSTransport([[]])

        result = RouterOSExecutor(transport).execute(operation)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "LOOKUP_NOT_FOUND")
        self.assertEqual(len(transport.requests), 1)

    def test_unsupported_operation_returns_error_without_transport_call(self):
        operation = build_operation("network.system.reboot.run", target="router-01")
        transport = FakeRouterOSTransport([])

        result = RouterOSExecutor(transport).execute(operation)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "UNSUPPORTED_OPERATION")
        self.assertEqual(transport.requests, [])


class RouterOSTopologyCollectionTests(unittest.TestCase):
    def test_collect_routeros_topology_reads_neighbors_and_bridge_ports(self):
        transport = FakeRouterOSTransport(
            [
                [
                    {
                        "address4": "192.168.0.10",
                        "identity": "tower-cpe-01",
                        "interface_name": "bridge1/ether2",
                        "mac_address": "74:4D:28:35:62:1B",
                    }
                ],
                [
                    {
                        "interface": "ether2",
                        "bridge": "bridge1",
                        "disabled": "false",
                        "inactive": "true",
                        "status": "inactive",
                    }
                ],
            ]
        )

        result = collect_routeros_topology(RouterOSExecutor(transport), "edge-01")

        self.assertTrue(result.ok)
        self.assertEqual(result.operation, "network.topology.snapshot.observe")
        self.assertEqual(result.data.attachments[0].interface, "ether2")
        self.assertEqual(result.data.interface_states[0].interface, "ether2")
        self.assertTrue(result.data.interface_states[0].inactive)
        self.assertFalse(result.data.interface_states[0].running)
        self.assertEqual(
            [request["path"] for request in transport.requests],
            ["/ip/neighbor", "/interface/bridge/port"],
        )
        self.assertEqual(
            result.to_dict()["data"]["interface_states"][0]["status"],
            "inactive",
        )

    def test_preflight_routeros_operation_uses_live_interface_state(self):
        transport = FakeRouterOSTransport(
            [
                [],
                [
                    {
                        "interface": "ether2",
                        "bridge": "bridge1",
                        "disabled": "false",
                        "inactive": "true",
                        "status": "inactive",
                    }
                ],
            ]
        )
        operation = build_operation(
            "network.interfaces.disable",
            target="edge-01",
            name="ether2",
        )

        result = preflight_routeros_operation(RouterOSExecutor(transport), operation)

        self.assertFalse(result.ok)
        self.assertEqual(result.capability, "preflight")
        self.assertEqual(result.error.code, "PREFLIGHT_RISK")
        self.assertEqual(
            result.data.risks,
            ("edge-01 ether2 (bridge1) is inactive",),
        )

    def test_preflight_routeros_operation_accepts_network_device_alias(self):
        transport = FakeRouterOSTransport(
            [
                [],
                [
                    {
                        "interface": "ether2",
                        "bridge": "bridge1",
                        "inactive": "true",
                        "status": "inactive",
                    }
                ],
            ]
        )
        operation = build_operation(
            "network.interfaces.disable",
            target="router-01",
            name="ether2",
        )

        result = preflight_routeros_operation(
            RouterOSExecutor(transport),
            operation,
            network_device="edge-01",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.target, "router-01")
        self.assertEqual(result.data.target, "edge-01")
        self.assertEqual(
            result.data.risks,
            ("edge-01 ether2 (bridge1) is inactive",),
        )


class RouterOSRestTransportTests(unittest.TestCase):
    def test_rest_transport_uses_ros_session_and_cleans_response_keys(self):
        response = FakeResponse(
            '[{".id": "*1", "dst-address": "0.0.0.0/0", "routing-table": "main"}]'
        )
        ros = FakeRos(response)

        data = RouterOSRestTransport(ros).request(
            "GET",
            "/ip/route",
            params={"dst-address": "0.0.0.0/0"},
        )

        self.assertTrue(response.raised)
        self.assertEqual(
            ros.session.calls,
            [
                (
                    "GET",
                    "https://router.example/rest/ip/route",
                    {"dst-address": "0.0.0.0/0"},
                    None,
                    False,
                )
            ],
        )
        self.assertEqual(
            data,
            [{"id": "*1", "dst_address": "0.0.0.0/0", "routing_table": "main"}],
        )


class RouterOSNormalizerTests(unittest.TestCase):
    def test_neighbor_rows_become_device_records(self):
        row = {
            "id": "*2",
            "address": "192.168.0.10",
            "address4": "192.168.0.10",
            "board": "RB941-2nD",
            "discovered_by": "mndp",
            "identity": "tower-cpe-01",
            "interface": "wlan2",
            "interface_name": "bridge1/ether2",
            "mac_address": "74:4D:28:35:62:1B",
            "platform": "MikroTik",
            "software_id": "F1BY-SY6F",
            "version": "6.49.19 (stable)",
        }

        devices = routeros_neighbors_to_devices([row])

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].name, "tower-cpe-01")
        self.assertEqual(devices[0].host, "192.168.0.10")
        self.assertEqual(devices[0].mac, "74:4D:28:35:62:1B")
        self.assertEqual(devices[0].serial, "F1BY-SY6F")
        self.assertEqual(devices[0].vendor, "MikroTik")
        self.assertIn("routeros:mndp/identity/tower-cpe-01", devices[0].identifiers)

    def test_neighbor_rows_become_attachment_records(self):
        row = {
            "address4": "192.168.0.10",
            "identity": "tower-cpe-01",
            "interface": "wlan2",
            "interface_name": "bridge1/ether2",
            "mac_address": "74:4D:28:35:62:1B",
        }

        attachments = routeros_neighbors_to_attachments([row], "router-01")

        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].network_device, "router-01")
        self.assertEqual(attachments[0].interface, "ether2")
        self.assertEqual(attachments[0].source, "routeros:/ip/neighbor")
        self.assertEqual(attachments[0].device.name, "tower-cpe-01")

    def test_neighbor_rows_normalize_bridge_member_interface_pairs(self):
        row = {
            "interface": "ether4,bridge1",
            "mac_address": "2C:F0:5D:DD:59:65",
        }

        attachments = routeros_neighbors_to_attachments([row], "router-01")

        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].interface, "ether4")
        self.assertEqual(attachments[0].metadata["interface"], "ether4,bridge1")

    def test_arp_rows_become_device_and_attachment_records(self):
        row = {
            "address": "10.20.30.45",
            "mac_address": "AA:BB:CC:DD:EE:01",
            "interface": "bridge-customers",
            "dynamic": "true",
        }

        devices = routeros_arp_to_devices([row])
        attachments = routeros_arp_to_attachments([row], "tower-router-03")

        self.assertEqual(devices[0].host, "10.20.30.45")
        self.assertEqual(devices[0].mac, "AA:BB:CC:DD:EE:01")
        self.assertEqual(attachments[0].network_device, "tower-router-03")
        self.assertEqual(attachments[0].interface, "bridge-customers")
        self.assertEqual(attachments[0].source, "routeros:/ip/arp")

    def test_bridge_host_rows_become_attachment_records(self):
        row = {
            "mac_address": "AA:BB:CC:DD:EE:01",
            "interface": "ether4",
            "bridge": "bridge1",
            "vid": "10",
        }

        attachments = routeros_bridge_hosts_to_attachments([row], "poe-switch-01")

        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].device.mac, "AA:BB:CC:DD:EE:01")
        self.assertEqual(attachments[0].interface, "ether4")
        self.assertEqual(attachments[0].metadata["vid"], "10")

    def test_bridge_port_rows_become_interface_state_records(self):
        row = {
            "id": "*1",
            "interface": "ether2",
            "bridge": "bridge1",
            "disabled": "false",
            "inactive": "true",
            "status": "inactive",
            "hw": "yes",
        }

        states = routeros_bridge_ports_to_interface_states([row], "poe-switch-01")

        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].network_device, "poe-switch-01")
        self.assertEqual(states[0].interface, "ether2")
        self.assertEqual(states[0].scope, "bridge1")
        self.assertFalse(states[0].disabled)
        self.assertTrue(states[0].inactive)
        self.assertFalse(states[0].running)
        self.assertEqual(states[0].status, "inactive")
        self.assertEqual(states[0].source, "routeros:/interface/bridge/port")

    def test_bridge_port_running_can_be_derived_from_status(self):
        row = {
            "interface": "wlan3",
            "bridge": "bridge1",
            "disabled": "false",
            "status": "in-bridge",
            "forwarding": "true",
        }

        states = routeros_bridge_ports_to_interface_states([row], "poe-switch-01")

        self.assertFalse(states[0].inactive)
        self.assertTrue(states[0].running)
        self.assertEqual(states[0].status, "in-bridge")
        self.assertTrue(states[0].forwarding)

    def test_routeros_attachments_feed_preflight(self):
        operation = build_operation(
            "network.interfaces.disable",
            target="poe-switch-01",
            name="ether1",
        )
        expected = [
            AttachmentRecord(
                device=DeviceRecord(name="device1", mac="AA:BB:CC:DD:EE:01"),
                network_device="poe-switch-01",
                interface="ether1",
            )
        ]
        observed = routeros_bridge_hosts_to_attachments(
            [
                {
                    "mac_address": "AA:BB:CC:DD:EE:01",
                    "interface": "ether4",
                }
            ],
            "poe-switch-01",
        )

        report = preflight_interface_operation(operation, expected, observed)

        self.assertFalse(report.ok)
        self.assertIn("device1 expected on poe-switch-01 ether1", report.risks[0])
        self.assertIn("but observed on poe-switch-01 ether4", report.risks[0])


if __name__ == "__main__":
    unittest.main()
