from typing import Any, List
from ros._base import BaseModule, BaseProps


from .router import UsermanRouters
from .user import UsermanUsers


class UsermanModule(BaseModule):
    _router: BaseProps[UsermanRouters] = None
    _user: BaseProps[UsermanUsers] = None

    @property
    def routers(self):
        if not self._router:
            self._router = BaseProps(self.ros, "/user-manager/router", UsermanRouters)
        return self._router

    @property
    def user(self):
        if not self._user:
            self._user = BaseProps(self.ros, "/user-manager/user", UsermanUsers)
        return self._user
