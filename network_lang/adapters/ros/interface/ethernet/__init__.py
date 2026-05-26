from abc import ABC

from attrs import define

from ros._base import BaseProps

from .ethernet import InterfaceEthernet


@define
class EthernetModule(BaseProps[InterfaceEthernet]):
    _ethernet: BaseProps[InterfaceEthernet] = None

    @property
    def ethernet(self) -> BaseProps[InterfaceEthernet]:
        if not self._ethernet:
            self._ethernet = BaseProps(self.ros, "/interface/ethernet", InterfaceEthernet)
        return self._ethernet


__all__ = ["EthernetModule", "InterfaceEthernet"]

