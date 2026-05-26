from attr import dataclass, field


@dataclass
class UsermanUsers:
    name: str
    password: str
    opt_secret: str = None
    group: str = None
    caller_id: str = None
    shared_users: int = None
    attributes: str = field(on_setattr=None, default=None)
    mikrotik_wireless_skip_dot1x: str = field(on_setattr=None, default=None)
    delegated_ipv6_prefix: str = field(on_setattr=None, default=None)
    framed_ip_netmask: str = field(on_setattr=None, default=None)
    framed_ipv6_pool: str = field(on_setattr=None, default=None)
    framed_pool: str = field(on_setattr=None, default=None)
    mikrotik_tunnel_medium_type: str = field(on_setattr=None, default=None)
    tunnel_type: str = field(on_setattr=None, default=None)
    acct_interim_interval: str = field(on_setattr=None, default=None)
    framed_ip_address: str = field(on_setattr=None, default=None)
    framed_ipv6_address: str = field(on_setattr=None, default=None)
    framed_ipv6_prefix: str = field(on_setattr=None, default=None)
    idle_timeout: str = field(on_setattr=None, default=None)
    session_timeout: str = field(on_setattr=None, default=None)
    tunnel_private_group_id: str = field(on_setattr=None, default=None)
