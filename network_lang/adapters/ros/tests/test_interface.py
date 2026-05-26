from ros import Ros, InterfaceModule
from ros.interface.bridge import BridgeModule, Bridge, BridgeMsti, BridgePort, BridgeVlan
from ros.interface.ethernet import EthernetModule
from ros.interface.list import InterfaceListModule, InterfaceList, InterfaceListMember


class TestInterface:
    def test_interface(self, ros: Ros):
        assert isinstance(ros.interface, InterfaceModule)


class TestBridge:
    def test_bridge(self, ros: Ros):
        assert isinstance(ros.interface.bridge, BridgeModule)

    def test_bridge_bridge(self, ros: Ros):
        for item in ros.interface.bridge():
            assert isinstance(item, Bridge)

    def test_bridge_msti(self, ros: Ros):
        for item in ros.interface.bridge.msti():
            assert isinstance(item, BridgeMsti)

    def test_bridge_port(self, ros: Ros):
        for item in ros.interface.bridge.port():
            assert isinstance(item, BridgePort)

    def test_bridge_vlan(self, ros: Ros):
        for item in ros.interface.bridge.vlan():
            assert isinstance(item, BridgeVlan)


class TestEthernet:
    def test_ethernet(self, ros: Ros):
        assert ros.interface.ethernet.cl == EthernetModule

    def test_ethernet_list(self, ros: Ros):
        for item in ros.interface.ethernet():
            assert isinstance(item, EthernetModule)


class TestList:
    def test_list(self, ros: Ros):
        assert isinstance(ros.interface.list, InterfaceListModule)

    def test_list_list(self, ros: Ros):
        for item in ros.interface.list.print():
            assert isinstance(item, InterfaceList)

    def test_list_member(self, ros: Ros):
        for item in ros.interface.list.member():
            assert isinstance(item, InterfaceListMember)
