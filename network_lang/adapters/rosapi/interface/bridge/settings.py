from attr import dataclass,  field
from typing import Union
from typing import Optional

@dataclass
class BridgeSettings:
    use_ip_firewall: Optional[str] = field(default=None)
    use_ip_firewall_for_vlan: Optional[str] = field(default=None)
    allow_fast_path: Optional[str] = field(default=None)
    use_ip_firewall_for_pppoe: Optional[str] = field(default=None)
    id: Union[str, None] = None

    