from network_lang import build_operation, preflight_interface_operation
from network_lang.adapters import (
    RouterOSExecutor,
    RouterOSRestTransport,
    collect_routeros_topology,
)
from network_lang.adapters.ros import Ros


TARGET = "edge-01"
PREFLIGHT_INTERFACE = "veth1"


ros = Ros("https://192.168.4.1/", "admin", "admin", secure=False)
executor = RouterOSExecutor(RouterOSRestTransport(ros))

snapshot_result = collect_routeros_topology(executor, TARGET)
if not snapshot_result.ok:
    print(snapshot_result.to_dict())
    raise SystemExit(1)

snapshot = snapshot_result.data

print("attachments")
for attachment in snapshot.attachments:
    print(attachment)

print("\ninterface states")
for state in snapshot.interface_states:
    print(state)

operation = build_operation(
    "network.interfaces.disable",
    target=TARGET,
    name=PREFLIGHT_INTERFACE,
)
preflight = preflight_interface_operation(
    operation,
    expected=[],
    observed=snapshot.attachments,
    interface_states=snapshot.interface_states,
)

print("\npreflight")
print(preflight.to_dict())
