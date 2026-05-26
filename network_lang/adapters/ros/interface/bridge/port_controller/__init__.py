from attrs import define

from ros._base import BaseProps

from .port_controller import PortController



@define
class PortControllerModule(BaseProps[PortController]):
	_port_controller: BaseProps[PortController] = None
	
	
	@property
	def port_controller(self) -> BaseProps[PortController]:
		if not self._port_controller:
			self._port_controller = BaseProps(self.ros, "/interface/bridge/port-controller", PortController)
		return self._port_controller


__all__ = ["PortController"]
