# /mikrotik: /routing/bgp/connection*
from typing import Optional, List
from attr import dataclass, field


from typing import Optional, List
from dataclasses import dataclass, field, asdict

@dataclass
class LocalConfig:
    address: Optional[str] = None
    port: Optional[int] = None
    role: Optional[str] = None
    ttl: Optional[int] = None

@dataclass
class RemoteConfig:
    allowed_as: Optional[List[int]] = field(default_factory=list)
    address: Optional[str] = None
    asn: Optional[int] = None
    port: Optional[int] = None
    ttl: Optional[int] = None

@dataclass
class Connection:
    local: LocalConfig = field(default_factory=LocalConfig)
    remote: RemoteConfig = field(default_factory=RemoteConfig)
    add_path_out: Optional[int] = None
    afi: Optional[str] = None
    asn: Optional[int] = None
    comment: Optional[str] = None
    hold_time: Optional[int] = None
    keepalive_time: Optional[int] = None
    name: Optional[str] = None
    multihop: Optional[bool] = None
    router_id: Optional[str] = None
    use_bfd: Optional[bool] = None

    def to_routeros_dict(self):
        """Convert dataclass to MikroTik API parameter dictionary."""
        data = {}
        if self.name: data["name"] = self.name
        if self.asn: data["as"] = self.asn
        if self.local.address: data["local.address"] = self.local.address
        if self.local.port: data["local.port"] = self.local.port
        if self.remote.address: data["remote.address"] = self.remote.address
        if self.remote.asn: data["remote.as"] = self.remote.asn
        if self.remote.port: data["remote.port"] = self.remote.port
        if self.hold_time: data["hold-time"] = self.hold_time
        if self.keepalive_time: data["keepalive-time"] = self.keepalive_time
        if self.multihop is not None: data["multihop"] = "yes" if self.multihop else "no"
        if self.router_id: data["router-id"] = self.router_id
        if self.use_bfd is not None: data["use-bfd"] = "yes" if self.use_bfd else "no"
        return data

    def add_to_routeros(self, ip: str, username: str, password: str):
        """Push connection to MikroTik RouterOS via API."""
        from ros import Ros
        ros = Ros(f"https://{ip}", username, password)
        params = self.to_routeros_dict()
        return ros.routing.bgp.connection.add(**params)