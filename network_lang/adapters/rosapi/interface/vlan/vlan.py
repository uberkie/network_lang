from attr import dataclass, field
from typing import Union


@dataclass
class InterfaceVlan:
    name: Union[str, None]
    vlan_id: Union[int, None]
    use_service_tag: bool = None
    interface: str = field(on_setattr=None, default=None)
    ARP: str = field(on_setattr=None, default=None)
    disabled: str = field(on_setattr=None, default=None)
    enabled: str = field(on_setattr=None, default=None)
    local_proxy_arp: str = field(on_setattr=None, default=None)
    proxy_arp: str = field(on_setattr=None, default=None)
    reply_only: str = field(on_setattr=None, default=None)

    def __str__(self) -> str:
        return self.name

    def __bool__(self) -> bool:
        return not self.disabled
