from typing import Optional
from attr import dataclass, field


@dataclass
class PortController:
	bridge: Optional[str] = field(default=None)
	disabled: Optional[str] = field(default=None)
	cascade_ports: Optional[str] = field(default=None)
	switch: Optional[str] = field(default=None)
	id: Optional[str] = field(default=None)
	
	
	def __bool__(self) -> bool:
		value = (self.disabled or "").strip().lower()
		return value not in {"true", "yes", "1"}