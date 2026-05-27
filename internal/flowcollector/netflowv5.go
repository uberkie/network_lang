package flowcollector

import (
	"encoding/binary"
	"errors"
	"fmt"
	"net/netip"
	"time"
)

const (
	NetFlowV5HeaderLen = 24
	NetFlowV5RecordLen = 48
)

type EndpointMode string

const (
	EndpointSrc  EndpointMode = "src"
	EndpointDst  EndpointMode = "dst"
	EndpointBoth EndpointMode = "both"
)

type NetFlowV5Header struct {
	Version          uint16
	Count            uint16
	SysUptime        uint32
	UnixSecs         uint32
	UnixNsecs        uint32
	FlowSequence     uint32
	EngineType       uint8
	EngineID         uint8
	SamplingInterval uint16
}

type NetFlowV5Record struct {
	SrcAddr  netip.Addr
	DstAddr  netip.Addr
	NextHop  netip.Addr
	Input    uint16
	Output   uint16
	Packets  uint32
	Bytes    uint32
	First    uint32
	Last     uint32
	SrcPort  uint16
	DstPort  uint16
	TCPFlags uint8
	Protocol uint8
	TOS      uint8
	SrcAS    uint16
	DstAS    uint16
	SrcMask  uint8
	DstMask  uint8
}

type NetFlowV5Packet struct {
	Header  NetFlowV5Header
	Records []NetFlowV5Record
}

type DeviceRecord struct {
	Name        *string        `json:"name"`
	Host        string         `json:"host"`
	MAC         *string        `json:"mac"`
	Serial      *string        `json:"serial"`
	Vendor      *string        `json:"vendor"`
	Platform    *string        `json:"platform"`
	Source      string         `json:"source"`
	Identifiers []string       `json:"identifiers"`
	Metadata    map[string]any `json:"metadata"`
}

func DecodeNetFlowV5(datagram []byte) (NetFlowV5Packet, error) {
	if len(datagram) < NetFlowV5HeaderLen {
		return NetFlowV5Packet{}, fmt.Errorf("netflow v5 packet too short: %d bytes", len(datagram))
	}

	version, err := NetFlowVersion(datagram)
	if err != nil {
		return NetFlowV5Packet{}, err
	}
	header := NetFlowV5Header{
		Version:          version,
		Count:            binary.BigEndian.Uint16(datagram[2:4]),
		SysUptime:        binary.BigEndian.Uint32(datagram[4:8]),
		UnixSecs:         binary.BigEndian.Uint32(datagram[8:12]),
		UnixNsecs:        binary.BigEndian.Uint32(datagram[12:16]),
		FlowSequence:     binary.BigEndian.Uint32(datagram[16:20]),
		EngineType:       datagram[20],
		EngineID:         datagram[21],
		SamplingInterval: binary.BigEndian.Uint16(datagram[22:24]),
	}
	if header.Version != 5 {
		return NetFlowV5Packet{}, fmt.Errorf("unsupported netflow version: %d", header.Version)
	}

	want := NetFlowV5HeaderLen + int(header.Count)*NetFlowV5RecordLen
	if len(datagram) < want {
		return NetFlowV5Packet{}, fmt.Errorf("netflow v5 packet count needs %d bytes, got %d", want, len(datagram))
	}

	records := make([]NetFlowV5Record, 0, header.Count)
	offset := NetFlowV5HeaderLen
	for i := 0; i < int(header.Count); i++ {
		record := datagram[offset : offset+NetFlowV5RecordLen]
		records = append(records, NetFlowV5Record{
			SrcAddr:  addr(record[0:4]),
			DstAddr:  addr(record[4:8]),
			NextHop:  addr(record[8:12]),
			Input:    binary.BigEndian.Uint16(record[12:14]),
			Output:   binary.BigEndian.Uint16(record[14:16]),
			Packets:  binary.BigEndian.Uint32(record[16:20]),
			Bytes:    binary.BigEndian.Uint32(record[20:24]),
			First:    binary.BigEndian.Uint32(record[24:28]),
			Last:     binary.BigEndian.Uint32(record[28:32]),
			SrcPort:  binary.BigEndian.Uint16(record[32:34]),
			DstPort:  binary.BigEndian.Uint16(record[34:36]),
			TCPFlags: record[37],
			Protocol: record[38],
			TOS:      record[39],
			SrcAS:    binary.BigEndian.Uint16(record[40:42]),
			DstAS:    binary.BigEndian.Uint16(record[42:44]),
			SrcMask:  record[44],
			DstMask:  record[45],
		})
		offset += NetFlowV5RecordLen
	}

	return NetFlowV5Packet{Header: header, Records: records}, nil
}

func NetFlowVersion(datagram []byte) (uint16, error) {
	if len(datagram) < 2 {
		return 0, fmt.Errorf("netflow packet too short: %d bytes", len(datagram))
	}
	return binary.BigEndian.Uint16(datagram[0:2]), nil
}

func DeviceRecords(
	packet NetFlowV5Packet,
	exporter string,
	receivedAt time.Time,
	endpoint EndpointMode,
) ([]DeviceRecord, error) {
	if endpoint != EndpointSrc && endpoint != EndpointDst && endpoint != EndpointBoth {
		return nil, errors.New("endpoint must be src, dst, or both")
	}

	records := make([]DeviceRecord, 0, len(packet.Records))
	for _, flow := range packet.Records {
		if endpoint == EndpointSrc || endpoint == EndpointBoth {
			records = append(records, deviceRecord(packet, flow, exporter, receivedAt, "src"))
		}
		if endpoint == EndpointDst || endpoint == EndpointBoth {
			records = append(records, deviceRecord(packet, flow, exporter, receivedAt, "dst"))
		}
	}
	return records, nil
}

func deviceRecord(
	packet NetFlowV5Packet,
	flow NetFlowV5Record,
	exporter string,
	receivedAt time.Time,
	direction string,
) DeviceRecord {
	host := flow.SrcAddr.String()
	peer := flow.DstAddr.String()
	interfaceIndex := flow.Input
	if direction == "dst" {
		host = flow.DstAddr.String()
		peer = flow.SrcAddr.String()
		interfaceIndex = flow.Output
	}

	return DeviceRecord{
		Host:        host,
		Source:      "netflow:v5",
		Identifiers: []string{},
		Metadata: map[string]any{
			"exporter":               exporter,
			"direction":              direction,
			"peer_host":              peer,
			"src_host":               flow.SrcAddr.String(),
			"dst_host":               flow.DstAddr.String(),
			"src_port":               flow.SrcPort,
			"dst_port":               flow.DstPort,
			"protocol":               flow.Protocol,
			"tos":                    flow.TOS,
			"tcp_flags":              flow.TCPFlags,
			"bytes":                  flow.Bytes,
			"packets":                flow.Packets,
			"next_hop":               flow.NextHop.String(),
			"interface_index":        interfaceIndex,
			"input_interface_index":  flow.Input,
			"output_interface_index": flow.Output,
			"first_switched_ms":      flow.First,
			"last_switched_ms":       flow.Last,
			"flow_sequence":          packet.Header.FlowSequence,
			"engine_type":            packet.Header.EngineType,
			"engine_id":              packet.Header.EngineID,
			"sampling_interval":      packet.Header.SamplingInterval,
			"received_at":            receivedAt.UTC().Format(time.RFC3339Nano),
		},
	}
}

func addr(raw []byte) netip.Addr {
	return netip.AddrFrom4([4]byte{raw[0], raw[1], raw[2], raw[3]})
}
