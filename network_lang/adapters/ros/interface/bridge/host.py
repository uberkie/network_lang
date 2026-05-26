from typing import Optional
from attr import dataclass, field

@dataclass
class BridgeHost:
    bridge: Optional[str] = field(default=None)
    disabled: Optional[str] = field(default=None)
    interface: Optional[str] = field(default=None)
    mac_address: Optional[str] = field(default=None)
    vid: Optional[str] = field(default=None)
    comment: Optional[str] = field(default=None)
    id: Optional[str] = field(default=None)
    
    
    def __bool__(self) -> bool:
        value = (self.disabled or "").strip().lower()
        return value not in {"true", "yes", "1"}