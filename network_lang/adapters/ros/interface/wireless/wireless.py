from dataclasses import field

from attr import dataclass
from typing import Union, Optional
from ros._literals import ARPLiteral


@dataclass
class Wireless:
    name: str
    disabled: bool
    arp: Union[ARPLiteral, None]
    mac_address: str
    actual_mtu: Union[int, None] = None
    l2mtu: Union[int, None] = None
    comment: Union[str, None] = None
    id: Union[str, None] = None
    interface_type: Optional[str] = field(default=None)
    mode: Optional[str] = field(default=None)
    ssid: Optional[str] = field(default=None)
    frequency: Optional[int] = field(default=None)
    band: Optional[str] = field(default=None)
    channel_width: Optional[str] = field(default=None)
    secondary_frequency: Optional[str] = field(default=None)
    scan_list: Optional[str] = field(default=None)
    wireless_protocol: Optional[str] = field(default=None)
    vlan_mode: Optional[str] = field(default=None)
    vlan_id: Optional[str] = field(default="1")
    wds_mode: Optional[str] = field(default=None)
    wds_default_bridge: Optional[str] = field(default=None)
    wds_ignore_ssid: Optional[str] = field(default=None)
    bridge_mode: Optional[str] = field(default=None)
    default_authentication: Optional[str] = field(default=None)
    default_forwarding: Optional[str] = field(default=None)
    default_ap_tx_limit: Optional[int] = field(default=0)
    default_client_tx_limit: Optional[int] = field(default=0)
    hide_ssid:  Optional[str] = field(default=None)
    security_profile: Optional[str] = field(default="default")

    def __str__(self) -> str:
        return self.name

    def __bool__(self) -> bool:
        return not self.disabled
