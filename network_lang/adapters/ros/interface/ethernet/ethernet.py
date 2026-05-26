from attr import dataclass
from typing import Union


@dataclass
class InterfaceEthernet:
    name: Union[str, None] = None
    l2mtu: Union[int, None] = None
    arp: Union[str, None] = None
    arp_timeout: Union[str, None] = None
    auto_negotiation: Union[bool, None] = None
    bandwidth: Union[str, None] = None
    default_name: Union[str, None] = None
    disabled: Union[bool, None] = None
    driver_rx_byte: Union[int, None] = None
    driver_rx_packet: Union[int, None] = None
    driver_tx_byte: Union[int, None] = None
    driver_tx_packet: Union[int, None] = None

    loop_protect: Union[str, None] = None
    loop_protect_disable_time: Union[str, None] = None
    loop_protect_send_interval: Union[str, None] = None
    loop_protect_status: Union[str, None] = None
    mac_address: Union[str, None] = None
    mtu: Union[int, None] = None

    orig_mac_address: Union[str, None] = None
    running: Union[bool, None] = None
    rx_broadcast: Union[int, None] = None
    rx_bytes: Union[int, None] = None
    rx_fcs_error: Union[int, None] = None
    rx_flow_control: Union[str, None] = None
    rx_fragment: Union[int, None] = None
    rx_jabber: Union[int, None] = None
    rx_multicast: Union[int, None] = None
    rx_pause: Union[int, None] = None
    tx_broadcast: Union[int, None] = None
    tx_bytes: Union[int, None] = None
    tx_flow_control: Union[str, None] = None
    tx_multicast: Union[int, None] = None
    tx_pause: Union[int, None] = None
    advertise: Union[str, None] = None
    full_duplex: Union[bool, None] = None
    speed: Union[str, None] = None
    comment: Union[str, None] = None
    fec_mode: Union[str, None] = None
    rx_1024_1518: Union[int, None] = None
    rx_128_255: Union[int, None] = None
    rx_1519_max: Union[int, None] = None
    rx_256_511: Union[int, None] = None
    rx_512_1023: Union[int, None] = None
    rx_64: Union[int, None] = None
    rx_65_127: Union[int, None] = None
    rx_align_error: Union[int, None] = None
    rx_drop: Union[int, None] = None
    rx_length_error: Union[int, None] = None
    rx_packet: Union[int, None] = None
    rx_too_long: Union[int, None] = None
    rx_too_short: Union[int, None] = None
    sfp_rate_select: Union[str, None] = None
    slave: Union[bool, None] = None
    switch: Union[str, None] = None
    tx_1024_1518: Union[int, None] = None
    tx_128_255: Union[int, None] = None
    tx_256_511: Union[int, None] = None
    tx_512_1023: Union[int, None] = None
    tx_64: Union[int, None] = None
    tx_65_127: Union[int, None] = None
    tx_collision: Union[int, None] = None
    tx_deferred: Union[int, None] = None
    tx_drop: Union[int, None] = None
    tx_excessive_collision: Union[int, None] = None
    tx_fcs_error: Union[int, None] = None
    tx_late_collision: Union[int, None] = None
    tx_multiple_collision: Union[int, None] = None
    tx_packet: Union[int, None] = None
    tx_single_collision: Union[int, None] = None
    id: Union[str, None] = None

    def __str__(self) -> str:
        return self.name

    def __bool__(self) -> bool:
        return not self.disabled
