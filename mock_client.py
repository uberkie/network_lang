from network_lang import target_device


TARGET = "https://192.168.4.1/"
PREFLIGHT_INTERFACE = "veth1"

device = target_device(TARGET)

snapshot_result = device.collect_topology()
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

preflight = device.preflight(
    "network.interfaces.disable",
    name=PREFLIGHT_INTERFACE,
)

print("\npreflight")
print(preflight.to_dict())
