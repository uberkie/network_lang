package flowcollector

import (
	"encoding/binary"
	"testing"
	"time"
)

func TestDecodeNetFlowV5(t *testing.T) {
	packet, err := DecodeNetFlowV5(samplePacket())
	if err != nil {
		t.Fatalf("DecodeNetFlowV5() error = %v", err)
	}

	if packet.Header.Version != 5 {
		t.Fatalf("version = %d", packet.Header.Version)
	}
	if len(packet.Records) != 1 {
		t.Fatalf("records = %d", len(packet.Records))
	}

	record := packet.Records[0]
	if got := record.SrcAddr.String(); got != "10.20.30.45" {
		t.Fatalf("src addr = %s", got)
	}
	if got := record.DstAddr.String(); got != "8.8.8.8" {
		t.Fatalf("dst addr = %s", got)
	}
	if record.Input != 17 || record.Output != 3 {
		t.Fatalf("interfaces = %d/%d", record.Input, record.Output)
	}
	if record.Packets != 40 || record.Bytes != 12000 {
		t.Fatalf("counters = %d/%d", record.Packets, record.Bytes)
	}
}

func TestNetFlowVersion(t *testing.T) {
	version, err := NetFlowVersion(samplePacket())
	if err != nil {
		t.Fatalf("NetFlowVersion() error = %v", err)
	}
	if version != 5 {
		t.Fatalf("version = %d", version)
	}
}

func TestDeviceRecordsSrc(t *testing.T) {
	packet, err := DecodeNetFlowV5(samplePacket())
	if err != nil {
		t.Fatalf("DecodeNetFlowV5() error = %v", err)
	}
	receivedAt := time.Date(2026, 5, 27, 1, 2, 3, 4, time.UTC)

	records, err := DeviceRecords(packet, "192.0.2.10", receivedAt, EndpointSrc)
	if err != nil {
		t.Fatalf("DeviceRecords() error = %v", err)
	}
	if len(records) != 1 {
		t.Fatalf("records = %d", len(records))
	}

	record := records[0]
	if record.Host != "10.20.30.45" {
		t.Fatalf("host = %s", record.Host)
	}
	if record.Source != "netflow:v5" {
		t.Fatalf("source = %s", record.Source)
	}
	if record.Metadata["direction"] != "src" {
		t.Fatalf("direction = %v", record.Metadata["direction"])
	}
	if record.Metadata["peer_host"] != "8.8.8.8" {
		t.Fatalf("peer_host = %v", record.Metadata["peer_host"])
	}
	if record.Metadata["interface_index"] != uint16(17) {
		t.Fatalf("interface_index = %v", record.Metadata["interface_index"])
	}
	if record.Metadata["received_at"] != "2026-05-27T01:02:03.000000004Z" {
		t.Fatalf("received_at = %v", record.Metadata["received_at"])
	}
}

func TestDeviceRecordsBoth(t *testing.T) {
	packet, err := DecodeNetFlowV5(samplePacket())
	if err != nil {
		t.Fatalf("DecodeNetFlowV5() error = %v", err)
	}

	records, err := DeviceRecords(packet, "192.0.2.10", time.Time{}, EndpointBoth)
	if err != nil {
		t.Fatalf("DeviceRecords() error = %v", err)
	}
	if len(records) != 2 {
		t.Fatalf("records = %d", len(records))
	}
	if records[0].Host != "10.20.30.45" || records[1].Host != "8.8.8.8" {
		t.Fatalf("hosts = %s/%s", records[0].Host, records[1].Host)
	}
}

func samplePacket() []byte {
	packet := make([]byte, NetFlowV5HeaderLen+NetFlowV5RecordLen)

	binary.BigEndian.PutUint16(packet[0:2], 5)
	binary.BigEndian.PutUint16(packet[2:4], 1)
	binary.BigEndian.PutUint32(packet[4:8], 123456)
	binary.BigEndian.PutUint32(packet[8:12], 1779847200)
	binary.BigEndian.PutUint32(packet[16:20], 42)
	packet[20] = 1
	packet[21] = 2
	binary.BigEndian.PutUint16(packet[22:24], 100)

	record := packet[NetFlowV5HeaderLen:]
	copy(record[0:4], []byte{10, 20, 30, 45})
	copy(record[4:8], []byte{8, 8, 8, 8})
	copy(record[8:12], []byte{192, 0, 2, 1})
	binary.BigEndian.PutUint16(record[12:14], 17)
	binary.BigEndian.PutUint16(record[14:16], 3)
	binary.BigEndian.PutUint32(record[16:20], 40)
	binary.BigEndian.PutUint32(record[20:24], 12000)
	binary.BigEndian.PutUint32(record[24:28], 1000)
	binary.BigEndian.PutUint32(record[28:32], 5000)
	binary.BigEndian.PutUint16(record[32:34], 54321)
	binary.BigEndian.PutUint16(record[34:36], 53)
	record[37] = 0x10
	record[38] = 17
	record[39] = 0

	return packet
}
