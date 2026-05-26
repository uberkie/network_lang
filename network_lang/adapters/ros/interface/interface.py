from dataclasses import field

from attr import dataclass
from typing import Union, Optional

import cattrs
from cattrs import Converter
from typing import Union

# Define the structure hook
from cattrs.converters import NoneType


@dataclass
class Interface:
    mtu: Optional[int]
    name: Optional[str] = None
    running: Optional[bool] = None
    rx_byte: Optional[int] = None
    rx_drop: Optional[int] = None
    rx_error: Optional[int] = None
    rx_packet: Optional[int] = None
    tx_byte: Optional[int] = None
    tx_drop: Optional[int] = None
    tx_error: Optional[int] = None
    tx_packet: Optional[int] = None
    tx_queue_drop: Optional[int] = None
    type: Optional[str] = None
    comment: [str] = None
    l2mtu: Optional[int] = None
    mac_address: str = None
    default_name: Optional[str] = None
    max_l2mtu: Optional[int] = None
    slave: Optional[bool] = None
    id: Optional[str] = None
    actual_mtu: Optional[int] = None
    disabled: Optional[bool] = None
    fp_rx_byte: Optional[int] = None
    fp_rx_packet: Optional[int] = None

    fp_tx_byte: Optional[int] = None
    fp_tx_packet: Optional[int] = None
    link_downs: Optional[int] = None

    def __str__(self) -> str:
        return self.name

    def __bool__(self) -> bool:
        return not self.disabled

