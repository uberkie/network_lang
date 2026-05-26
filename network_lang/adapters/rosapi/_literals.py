from typing import Literal

AllLiteral = Literal["all"]
AnyLiteral = Literal["any"]
ARPLiteral = Literal[
    "disabled", "enabled", "local-proxy-arp", "proxy-arp", "reply-only"
]
IPProtocol = Literal[
    "ah",  # Authentication Header
    "esp",  # Encapsulating Security Payload
    "icmp", "icmpv6",
    "igmp", "gre", "ospf",
    "ipip", "tcp", "udp", "sctp",
    "vrrp", "pim", "l2tp",
    "ipsec-ah", "ipsec-esp", "rsvp", "encap",
    "egp", "hmp", "ddp", "st", "vmtp", "xns-idp",
    "xtp", "udp-lite", "ipv6-encap", "ipv6-route", "ipv6-frag", "ipv6-nonxt", "ipv6-opts",
]

MACProtocol = Literal[
    "arp", "rarp", "ip", "ipv6", "lldp", "loop-protect",
    "pppoe", "pppoe-discovery",
    "mpls-unicast", "mpls-multicast",
    "vlan", "service-vlan", "packing-compr", "packing-simple",
    "homeplug-av", "ipx", "802.2", "bridge"
]

PortLiteral = Literal[
    "custom", "api", "api-ssl", "www", "www-ssl", "dns", "dhcp", "dhcp6", "snmp", "ntp", "syslog", "ssh", "ftp", "tftp",
    "winbox", "winbox-old", "winbox-old-tls", "webfig"
]
RouterManagementPort = Literal[
    "winbox", "winbox-old", "winbox-old-tls", "webfig", "api", "api-ssl", "www", "www-ssl"
]
TCPState = Literal[
    "established", "syn-sent", "syn-recv", "fin-wait",
    "time-wait", "close", "close-wait", "last-ack", "listen",
    "none", "unknown"
]

InterfaceType = Literal[
    "ether", "bridge", "vlan", "pppoe-client", "lte", "gre", "eoip", "wireguard",
    "wlan", "wlan1", "wlan2", "vrrp", "bonding", "loopback",
    "ovpn-client", "ovpn-server", "pptp-client", "pptp-server", "sstp-client", "sstp-server",
    "l2tp-client", "l2tp-server", "mesh", "dummy", "ipoe", "cap", "mac-telnet", "wg"
]

LeaseStatus = Literal["bound", "offered", "expired", "released", "waiting"]

AddressFamily = Literal[
    "ipv4", "ipv6", "ip", "mpls"
]

ChainType = Literal[
    "input", "forward", "output", "prerouting", "postrouting",  # base
    "srcnat", "dstnat",  # NAT
    "input", "output",  # Filter
    "hotspot", "unused"  # Special/edge cases
]

NATAction = Literal[
    "masquerade", "accept", "drop", "dst-nat", "src-nat", "redirect", "log", "netmap",
    "reject", "return", "tarpit", "mark-connection", "mark-packet", "mark-routing", "passthrough"
]

HorizonValue = Literal["none", "auto", "1", "2", "3", "4", "5"]

AuthMode = Literal["none", "static-keys-required", "dynamic-keys", "radius"]

WirelessMode = Literal[
    "station", "station-bridge", "ap-bridge", "bridge", "wds-slave",
    "station-wds", "station-pseudobridge", "station-pseudobridge-clone"
]

EncryptionType = Literal[
    "none", "wep", "tkip", "aes-ccm", "aes-gcm", "aes", "sha1", "sha256", "sha512", "md5", "blowfish"
]

LeaseType = Literal["dynamic", "static"]

LogPrefix = Literal["info", "warning", "error", "critical", "debug"]

