from typing import Any, List
from ros._base import BaseModule, BaseProps
from .bridge import BridgeModule, Bridge, BridgeMsti, BridgePort, BridgeVlan
from .ethernet import EthernetModule, InterfaceEthernet
from .interface import Interface
from .list import InterfaceListModule, InterfaceList
from .vlan import VlanModule
from .wireless import WirelessModule, Wireless
from .monitor import MonitorModule


class InterfaceModule(BaseModule):
    _bridge: BridgeModule = None
    _ethernet: EthernetModule = None
    _list: InterfaceListModule = None
    _vlan: VlanModule = None
    _wireless: WirelessModule = None
    _monitor: MonitorModule = None

    def __call__(self, **kwds: Any):
        return self.print(**kwds)

    @property
    def bridge(self) -> BridgeModule:
        if not self._bridge:
            self._bridge = BridgeModule(self.ros, "/interface/bridge", Bridge)
        return self._bridge

    @property
    def wireless(self) -> WirelessModule:
        if not self._wireless:
            self._wireless = WirelessModule(self.ros, "/interface/wireless", Wireless)
        return self._wireless

    @property
    def ethernet(self) -> EthernetModule:
        if not self._ethernet:
            self._ethernet = EthernetModule(self.ros, "/interface/ethernet", InterfaceEthernet)
        return self._ethernet

    @property
    def monitor(self) -> MonitorModule:
        if not self._monitor:
            self._monitor = MonitorModule(self.ros, "/interface/monitor", MonitorModule)
        return self._monitor


    @property
    def list(self) -> InterfaceListModule:
        if not self._list:
            self._list = InterfaceListModule(self.ros, "/interface/list", InterfaceList)
        return self._list

    def print(self, **kwds: Any) -> List[Interface]:
        return self.ros.get_as(self.url, List[Interface], kwds)


__all__ = [
    "BridgeModule",
    "EthernetModule",
    "InterfaceModule",
    "Interface",
    "InterfaceListModule",
    "VlanModule",
    "WirelessModule",
    "MonitorModule",
]
