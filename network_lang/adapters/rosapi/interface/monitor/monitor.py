from dataclasses import dataclass


@dataclass(slots=True)
class InterfaceMonitor:
    name: str
    rx_packets_per_second: str
    rx_bits_per_second: str
    fp_rx_packets_per_second: str
    fp_rx_bits_per_second: str
    rx_drops_per_second: str
    rx_errors_per_second: str
    tx_packets_per_second: str
    tx_bits_per_second: str
    fp_tx_packets_per_second: str
    fp_tx_bits_per_second: str
    tx_drops_per_second: str
    tx_queue_drops_per_second: str
    tx_errors_per_second: str

    def __bool__(self) -> bool:
        return bool(self.name)
