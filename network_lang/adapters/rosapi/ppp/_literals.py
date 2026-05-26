from enum import Enum
from typing import Union


class YesNoDefault(str, Enum):
    yes = "yes"
    no = "no"
    default = "default"


class YesNoDefaultRequired(str, Enum):
    yes = "yes"
    no = "no"
    required = "required"
    default = "default"

class PPPService(str, Enum):
    any = "any"
    asyncc = "async"
    l2tp = "l2tp"
    ovpn = "ovpn"
    pppoe = "pppoe"
    pptp = "pptp"
    sstp = "sstp"
    
class HorizonValue(str, Enum):
    auto = "auto"
    disabled = "disabled"

HorizonType = Union[HorizonValue, int]