from attrs import define

from ros._base import BaseProps

from .port_extender import PortExtender


@define
class PortExtenderModule(BaseProps[PortExtender]):
	_port_extender: BaseProps[PortExtender] = None
	
	
	@property
	def port_extender(self) -> BaseProps[PortExtender]:
		if not self._port_extender:
			self._port_extender = BaseProps(self.ros, "/interface/bridge/port-extender", PortExtender)
		return self._port_extender


__all__ = ["PortExtender"]
