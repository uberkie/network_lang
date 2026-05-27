package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"sync/atomic"
	"time"

	"network_lang/internal/flowcollector"
)

func main() {
	listen := flag.String("listen", ":2055", "UDP listen address")
	output := flag.String("output", "-", "JSONL output path, or - for stdout")
	endpoint := flag.String("endpoint", "src", "endpoint to emit: src, dst, or both")
	bufferSize := flag.Int("buffer", 9000, "UDP receive buffer size")
	debug := flag.Bool("debug", false, "log every received datagram")
	statusEvery := flag.Duration("status", 0, "status log interval, for example 10s; 0 disables")
	flag.Parse()

	writer, closeOutput, err := openOutput(*output)
	if err != nil {
		fatal(err)
	}
	defer closeOutput()

	addr, err := net.ResolveUDPAddr("udp", *listen)
	if err != nil {
		fatal(err)
	}
	conn, err := net.ListenUDP("udp", addr)
	if err != nil {
		fatal(err)
	}
	defer conn.Close()

	encoder := json.NewEncoder(writer)
	buffer := make([]byte, *bufferSize)
	mode := flowcollector.EndpointMode(*endpoint)
	var packets atomic.Uint64
	var decoded atomic.Uint64
	var recordsOut atomic.Uint64
	var decodeErrors atomic.Uint64

	if *statusEvery > 0 {
		go func() {
			ticker := time.NewTicker(*statusEvery)
			defer ticker.Stop()
			for range ticker.C {
				fmt.Fprintf(
					os.Stderr,
					"status packets=%d decoded=%d records=%d decode_errors=%d\n",
					packets.Load(),
					decoded.Load(),
					recordsOut.Load(),
					decodeErrors.Load(),
				)
			}
		}()
	}

	fmt.Fprintf(os.Stderr, "flowcollector listening on %s endpoint=%s output=%s\n", *listen, mode, *output)
	for {
		n, remote, err := conn.ReadFromUDP(buffer)
		if err != nil {
			fmt.Fprintf(os.Stderr, "read error: %v\n", err)
			continue
		}
		packets.Add(1)

		version, versionErr := flowcollector.NetFlowVersion(buffer[:n])
		if *debug {
			if versionErr != nil {
				fmt.Fprintf(os.Stderr, "rx %d bytes from %s version=unknown: %v\n", n, remote, versionErr)
			} else {
				fmt.Fprintf(os.Stderr, "rx %d bytes from %s version=%d\n", n, remote, version)
			}
		}

		packet, err := flowcollector.DecodeNetFlowV5(buffer[:n])
		if err != nil {
			decodeErrors.Add(1)
			fmt.Fprintf(os.Stderr, "decode error from %s: %v\n", remote, err)
			continue
		}
		decoded.Add(1)

		records, err := flowcollector.DeviceRecords(packet, remote.IP.String(), time.Now(), mode)
		if err != nil {
			fmt.Fprintf(os.Stderr, "record error from %s: %v\n", remote, err)
			continue
		}
		for _, record := range records {
			if err := encoder.Encode(record); err != nil {
				fmt.Fprintf(os.Stderr, "write error: %v\n", err)
				break
			}
			recordsOut.Add(1)
		}
	}
}

func openOutput(path string) (io.Writer, func(), error) {
	if path == "-" {
		return os.Stdout, func() {}, nil
	}

	file, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return nil, func() {}, err
	}
	return file, func() { _ = file.Close() }, nil
}

func fatal(err error) {
	fmt.Fprintf(os.Stderr, "flowcollector: %v\n", err)
	os.Exit(1)
}
