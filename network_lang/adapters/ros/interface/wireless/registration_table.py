from dataclasses import field

from attr import dataclass
from typing import Union, Optional



@dataclass
class RegistrationTable:
    interface: Optional[str] = field(default=None)
    mac_address: Optional[str] = field(default=None)
    ap: Optional[str] = field(default=None)
    signal_strength: Optional[str] = field(default=None)
    tx_rate: Optional[str] = field(default=None)
    uptime: Optional[str] = field(default=None)

    def __str__(self) -> str:
        return self.interface

