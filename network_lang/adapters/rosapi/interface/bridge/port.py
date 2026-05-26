from attr import dataclass
from typing import Union


@dataclass
class BridgePort:
    nextid: Union[str, None]
    auto_isolate: Union[bool, None]
    bpdu_guard: Union[bool, None]
    bridge: Union[str, None]
    broadcast_flood: Union[bool, None]
    disabled: Union[bool, None]
    dynamic: Union[bool, None]
    edge: Union[str, None]
    fast_leave: Union[bool, None]
    frame_types: Union[str, None]
    horizon: Union[str, None]
    inactive: Union[bool, None]
    ingress_filtering: Union[bool, None]
    interface: Union[str, None]
    internal_path_cost: Union[int, None]
    learn: Union[str, None]
    multicast_router: Union[str, None]
    path_cost: Union[int, None]
    point_to_point: Union[str, None]
    priority: Union[str, None]
    pvid: Union[int, None]
    restricted_role: Union[bool, None]
    restricted_tcn: Union[bool, None]
    status: Union[str, None]
    tag_stacking: Union[bool, None]
    trusted: Union[bool, None]
    unknown_multicast_flood: Union[bool, None]
    unknown_unicast_flood: Union[bool, None]
    comment: Union[str, None] = None
    id: Union[str, None] = None

    def __bool__(self) -> bool:
        return not self.disabled
