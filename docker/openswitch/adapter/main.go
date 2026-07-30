package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"

	pb "github.com/openconfig/gnmi/proto/gnmi"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

func main() {
	cfg := ParseConfig()
	log.Printf("adapter starting: gNMI=%s ovsdb=%s", cfg.GNMIListenAddr(), cfg.OVSDBSocket)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		sig := <-sigCh
		log.Printf("received signal %s, shutting down", sig)
		cancel()
	}()

	ovsClient := NewOVSDBClient(cfg)
	rateCalc := NewCounterRate(cfg.RateWindowSamples)
	prober := NewLatencyProber(cfg.LatencyTargets, cfg.LatencyInterval)

	if prober.Enabled() {
		go prober.Run(ctx)
	}

	go func() {
		if err := ovsClient.Run(ctx); err != nil && err != context.Canceled {
			log.Printf("ovsdb client error: %v", err)
		}
	}()

	select {
	case <-ovsClient.Ready():
		log.Printf("ovsdb client ready")
	case <-ctx.Done():
		log.Printf("adapter stopped before ovsdb connected")
		return
	}

	go feedRateCalc(ctx, ovsClient, rateCalc)

	gnmiSrv := NewGNMIServer(ovsClient, rateCalc, prober)

	tlsConfig, err := loadTLSConfig(cfg)
	if err != nil {
		log.Fatalf("tls: %v", err)
	}

	lis, err := net.Listen("tcp", cfg.GNMIListenAddr())
	if err != nil {
		log.Fatalf("listen: %v", err)
	}

	grpcSrv := grpc.NewServer(grpc.Creds(credentials.NewTLS(tlsConfig)))
	pb.RegisterGNMIServer(grpcSrv, gnmiSrv)

	go func() {
		log.Printf("gNMI server listening on %s (TLS)", cfg.GNMIListenAddr())
		if err := grpcSrv.Serve(lis); err != nil {
			log.Printf("gRPC server error: %v", err)
		}
	}()

	<-ctx.Done()

	log.Printf("shutting down gRPC server...")
	grpcSrv.GracefulStop()
	ovsClient.Close()
	log.Printf("adapter stopped")
}

func feedRateCalc(ctx context.Context, ovs *OVSDBClient, rc *CounterRate) {
	eventCh := ovs.Subscribe()
	defer ovs.Unsubscribe(eventCh)

	for {
		select {
		case <-ctx.Done():
			return
		case evt, ok := <-eventCh:
			if !ok {
				return
			}
			if evt.Table != "Interface" {
				continue
			}
			var iface *OVSDBInterface
			if evt.Op == "add" || evt.Op == "update" {
				iface, _ = evt.New.(*OVSDBInterface)
			}
			if iface == nil {
				continue
			}
			rc.RecordInterfaceStats(iface.Name, iface.Statistics)
		}
	}
}

func loadTLSConfig(cfg *Config) (*tls.Config, error) {
	cert, err := tls.LoadX509KeyPair(cfg.TLSCert, cfg.TLSKey)
	if err != nil {
		return nil, fmt.Errorf("load server cert/key: %w", err)
	}

	tlsConfig := &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS12,
	}

	if cfg.MTLSEnabled() {
		caPEM, err := os.ReadFile(cfg.TLSCA)
		if err != nil {
			return nil, fmt.Errorf("load CA cert: %w", err)
		}
		caPool := x509.NewCertPool()
		if !caPool.AppendCertsFromPEM(caPEM) {
			return nil, fmt.Errorf("failed to parse CA cert")
		}
		tlsConfig.ClientCAs = caPool
		tlsConfig.ClientAuth = tls.RequireAndVerifyClientCert
		log.Printf("mTLS enabled (CA: %s)", cfg.TLSCA)
	} else {
		log.Printf("mTLS disabled (server-side TLS only)")
	}

	return tlsConfig, nil
}
