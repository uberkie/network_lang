from attrs import define

from ros._base import BaseProps

from .wireless import Wireless
from .registration_table import RegistrationTable



@define
class WirelessModule(BaseProps[Wireless]):
    _registration_table: BaseProps[RegistrationTable] = None

    @property
    def registration_table(self) -> BaseProps[RegistrationTable]:
        if not self._registration_table:
            self._registration_table = BaseProps(self.ros, "/interface/wireless/registration-table", RegistrationTable)
        return self._registration_table


__all__ = ["WirelessModule", "Wireless", "RegistrationTable"]
