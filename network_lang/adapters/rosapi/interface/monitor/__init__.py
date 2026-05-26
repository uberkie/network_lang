from attrs import define
from ros._base import BaseProps
from .monitor import InterfaceMonitor


@define
class MonitorModule(BaseProps[InterfaceMonitor]):
    _monitor: BaseProps[InterfaceMonitor] = None

    @property
    def vlan(self) -> BaseProps[InterfaceMonitor]:
        if not self._monitor:
            self._monitor = BaseProps(self.ros, "/interface/monitor", InterfaceMonitor)
        return self._monitor


__all__ = ["MonitorModule"]
