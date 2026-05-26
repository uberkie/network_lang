from attr import dataclass
from typing import Union


@dataclass
class BridgeVlan:
    bridge: Union[str, None]
    current_tagged: Union[str, None]
    current_untagged: Union[str, None]
    disabled: Union[bool, None]
    dynamic: Union[bool, None]
    tagged: Union[str, None]
    untagged: Union[str, None]
    vlan_ids: Union[int, None]
    comment: Union[str, None] = None
    id: Union[str, None] = None

    def __bool__(self) -> bool:
        return not self.disabled
