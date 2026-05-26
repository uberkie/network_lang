from attr import dataclass
from typing import Union
from ros._literals import ARPLiteral


@dataclass
class Bridge:
    name: str
    arp: Union[ARPLiteral, None]
    ageing_time: str
    arp_timeout: str
    auto_mac: bool
    dhcp_snooping: bool
    disabled: bool
    fast_forward: bool
    forward_delay: str
    igmp_snooping: bool
    mac_address: str
    max_message_age: str
    mtu: str
    priority: str
    protocol_mode: str
    running: bool
    transmit_hold_count: Union[int, None]
    vlan_filtering: bool
    actual_mtu: Union[int, None] = None
    l2mtu: Union[int, None] = None
    comment: Union[str, None] = None
    id: Union[str, None] = None

    def __str__(self) -> str:
        return self.name

    def __bool__(self) -> bool:
        return not self.disabled
