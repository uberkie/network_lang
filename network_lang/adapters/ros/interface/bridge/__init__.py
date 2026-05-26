from attrs import define

from ros._base import BaseProps

from .bridge import Bridge
from .msti import BridgeMsti
from .port import BridgePort
from .vlan import BridgeVlan
from .host import BridgeHost
from .port_controller import PortController
from .port_extender import PortExtender
from .settings import BridgeSettings


@define
class BridgeModule(BaseProps[Bridge]):
    _msti: BaseProps[BridgeMsti] = None
    _port: BaseProps[BridgePort] = None
    _vlan: BaseProps[BridgeVlan] = None
    _host: BaseProps[BridgeHost] = None
    _port_controller: BaseProps[PortController] = None
    _port_extender: BaseProps[PortExtender] = None
    _settings: BaseProps[BridgeSettings] = None

    @property
    def msti(self) -> BaseProps[BridgeMsti]:
        if not self._msti:
            self._msti = BaseProps(self.ros, "/interface/bridge/msti", BridgeMsti)
        return self._msti

    @property
    def port(self) -> BaseProps[BridgePort]:
        if not self._port:
            self._port = BaseProps(self.ros, "/interface/bridge/port", BridgePort)
        return self._port

    @property
    def vlan(self) -> BaseProps[BridgeVlan]:
        if not self._vlan:
            self._vlan = BaseProps(self.ros, "/interface/bridge/vlan", BridgeVlan)
        return self._vlan

    @property
    def host(self) -> BaseProps[BridgeHost]:
        if not self._host:
            self._host = BaseProps(self.ros, "/interface/bridge/host", BridgeHost)
        return self._host

    @property
    def port_controller(self) -> BaseProps[PortController]:
        if not self._port_controller:
            self._port_controller = BaseProps(self.ros, "/interface/bridge/port-controller", PortController)
        return self._port_controller

    @property
    def port_extender(self) -> BaseProps[PortExtender]:
        if not self._port_extender:
            self._port_extender = BaseProps(self.ros, "/interface/bridge/port-extender", PortExtender)
        return self._port_extender

    @property
    def settings(self) -> BaseProps[BridgeSettings]:
        if not self._settings:
            self._settings = BaseProps(self.ros, "/interface/bridge/settings", BridgeSettings)
        return self._settings


__all__ = ["BridgeModule", "BridgePort", "Bridge", "BridgeHost", "BridgeVlan", "BridgeMsti", "PortController",
           "PortExtender", "BridgeSettings"]
