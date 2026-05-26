from attrs import define

from ros._base import BaseProps, BaseModule

from .advertisements import Advertisements
from .connection import Connection
from .session import Session
from .template import Template
from .vpls import VPLS
from .vpn import VPN


@define
class BGPModule(BaseModule):
    _advertisements: BaseProps[Advertisements] = None
    _connection: BaseProps[Connection] = None
    _session: BaseProps[Session] = None
    _template: BaseProps[Template] = None
    _vpls: BaseProps[VPLS] = None
    _vpn: BaseProps[VPN] = None

    @property
    def advertisements(self) -> BaseProps[Advertisements]:
        if not self._advertisements:
            self._advertisements = BaseProps(self.ros, "/routing/bgp/advertisements", Advertisements)
        return self._advertisements

    @property
    def connection(self) -> BaseProps[Connection]:
        if not self._connection:
            self._connection = BaseProps(self.ros, "/routing/bgp/connection", Connection)
        return self._connection

    @property
    def session(self) -> BaseProps[Session]:
        if not self._session:
            self._session = BaseProps(self.ros, "/routing/bgp/session", Session)
        return self._session

    @property
    def template(self) -> BaseProps[Template]:
        if not self._template:
            self._template = BaseProps(self.ros, "/routing/bgp/template", Template)
        return self._template

    @property
    def vpls(self) -> BaseProps[VPLS]:
        if not self._vpls:
            self._vpls = BaseProps(self.ros, "/routing/bgp/vpls", VPLS)
        return self._vpls

    @property
    def vpn(self) -> BaseProps[VPN]:
        if not self._vpn:
            self._vpn = BaseProps(self.ros, "/interface/bridge/port-extender", VPN)
        return self._vpn


__all__ = ["BGPModule", "Advertisements", "Connection", "Session", "Template", "VPN", "VPLS"]
