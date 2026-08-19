package main

import (
	"flag"
	"fmt"
	"strings"
)

type Config struct {
	OVSDBSocket       string
	GNMIAddr          string
	GNMIPort         int
	TLSCert          string
	TLSKey           string
	TLSCA            string
	LatencyTargets    []string
	LatencyTargetsFile string
	LatencyInterval   int
	RateWindowSamples int
}

func ParseConfig() *Config {
	cfg := &Config{}

	flag.StringVar(&cfg.OVSDBSocket, "ovsdb-socket", "/var/run/openvswitch/db.sock", "Path to OVSDB unix socket")
	flag.StringVar(&cfg.GNMIAddr, "gnmi-addr", "0.0.0.0", "gNMI server listen address")
	flag.IntVar(&cfg.GNMIPort, "gnmi-port", 9339, "gNMI server listen port")
	flag.StringVar(&cfg.TLSCert, "tls-cert", "/etc/ovs-gnmi-adapter/tls/server.crt", "TLS server certificate path")
	flag.StringVar(&cfg.TLSKey, "tls-key", "/etc/ovs-gnmi-adapter/tls/server.key", "TLS server key path")
	flag.StringVar(&cfg.TLSCA, "tls-ca", "", "TLS CA certificate path (enables mTLS if set)")
	flag.IntVar(&cfg.LatencyInterval, "latency-interval", 5, "Latency probe interval in seconds")
	flag.IntVar(&cfg.RateWindowSamples, "rate-window-samples", 5, "Number of counter samples to keep for rate computation")

	var latencyTargets string
	flag.StringVar(&latencyTargets, "latency-targets", "", "Comma-separated list of IPs to probe for latency (empty = disabled)")
	flag.StringVar(&cfg.LatencyTargetsFile, "latency-targets-file", "", "Path to a file of newline/comma-separated IPs to probe; re-read periodically (empty = unused)")

	flag.Parse()

	if latencyTargets != "" {
		cfg.LatencyTargets = strings.Split(latencyTargets, ",")
	}

	return cfg
}

func (c *Config) GNMIListenAddr() string {
	return fmt.Sprintf("%s:%d", c.GNMIAddr, c.GNMIPort)
}

func (c *Config) LatencyEnabled() bool {
	return len(c.LatencyTargets) > 0
}

func (c *Config) MTLSEnabled() bool {
	return c.TLSCA != ""
}
