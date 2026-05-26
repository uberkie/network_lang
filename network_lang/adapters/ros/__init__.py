__version__ = "0.0.1" # type: ignore

import sys as _sys

_sys.modules.setdefault("ros", _sys.modules[__name__])

try:
    from .interface import InterfaceModule
    from .ip import IPModule
    from .ppp import PPPModule
    from .queue import QueueModule
    from .routing import RoutingModule
    from .system import SystemModule
    from .tool import ToolModule, Ping
    from .user import UserModule
    from .error import Error
    from .log import Log
    from ros.ros import Ros
    from .userman import UsermanModule
    import ros._base
except ImportError:
    from .minimal import HTTPError as Error
    from .minimal import Ros

    InterfaceModule = None
    IPModule = None
    PPPModule = None
    QueueModule = None
    RoutingModule = None
    Log = None
    Ping = None
    SystemModule = None
    ToolModule = None
    UserModule = None
    UsermanModule = None
    _base = None

__all__ = [
    "Error",
    "InterfaceModule",
    "IPModule",
    "PPPModule",
    "QueueModule",
    "RoutingModule",
    "Log",
    "Ping",
    "Ros",
    "SystemModule",
    "ToolModule",
    "UserModule",
    "UsermanModule",
    "_base"
]
