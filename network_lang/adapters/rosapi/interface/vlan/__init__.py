from attrs import define
from ros._base import BaseProps
from .vlan import InterfaceVlan


@define
class VlanModule(BaseProps[InterfaceVlan]):
    _vlan: BaseProps[InterfaceVlan] = None

    @property
    def vlan(self) -> BaseProps[InterfaceVlan]:
        if not self._vlan:
            self._vlan = BaseProps(self.ros, "/interface/vlan", InterfaceVlan)
        return self._vlan


__all__ = ["VlanModule"]
