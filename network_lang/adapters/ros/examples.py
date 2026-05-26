# bgp connection
from ros.routing.bgp.connection import *
conn = Connection(
    name="Peer1",
    asn=65001,
    local=LocalConfig(address="192.0.2.1"),
    remote=RemoteConfig(address="192.0.2.2", asn=65002),
    multihop=False,
    hold_time=30
)

# Push to MikroTik
result = conn.add_to_routeros("10.0.0.1", "admin", "password")
print(result)
