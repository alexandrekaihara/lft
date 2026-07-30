package main

import (
	"context"
	"crypto/tls"
	"net"
	"testing"
	"time"

	pb "github.com/openconfig/gnmi/proto/gnmi"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

type mockOVSDB struct {
	interfaces []OVSDBInterface
	ports      []OVSDBPort
	bridges    []OVSDBBridge
	eventCh    chan OVSDBChangeEvent
}

func newMockOVSDB() *mockOVSDB {
	return &mockOVSDB{
		eventCh: make(chan OVSDBChangeEvent, 16),
	}
}

func (m *mockOVSDB) ListInterfaces() ([]OVSDBInterface, error) { return m.interfaces, nil }
func (m *mockOVSDB) ListPorts() ([]OVSDBPort, error)           { return m.ports, nil }
func (m *mockOVSDB) ListBridges() ([]OVSDBBridge, error)       { return m.bridges, nil }
func (m *mockOVSDB) Subscribe() chan OVSDBChangeEvent          { return m.eventCh }
func (m *mockOVSDB) Unsubscribe(ch chan OVSDBChangeEvent)      {}

func setupTestServer(t *testing.T) (*pb.GNMIClient, func()) {
	t.Helper()

	mock := newMockOVSDB()
	mock.bridges = []OVSDBBridge{
		{UUID: "br-uuid", Name: "br0", Ports: []string{"port-uuid"}},
	}
	mock.ports = []OVSDBPort{
		{UUID: "port-uuid", Name: "eth0", Interfaces: []string{"iface-uuid"}},
	}
	mock.interfaces = []OVSDBInterface{
		{
			UUID:       "iface-uuid",
			Name:       "eth0",
			Type:       "",
			LinkState:  "up",
			AdminState: "up",
			Statistics: map[string]int{
				"rx_bytes":   1000,
				"tx_bytes":   2000,
				"rx_packets": 10,
				"tx_packets": 20,
				"rx_dropped": 5,
				"tx_dropped": 3,
				"rx_errors":  1,
				"tx_errors":  2,
				"rx_crc_err": 4,
			},
		},
	}

	rateCalc := NewCounterRate(5)
	prober := NewLatencyProber(nil, 5)
	srv := NewGNMIServer(mock, rateCalc, prober)

	tlsConfig := generateTestTLSConfig(t)

	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}

	grpcSrv := grpc.NewServer(grpc.Creds(credentials.NewTLS(tlsConfig)))
	pb.RegisterGNMIServer(grpcSrv, srv)

	go grpcSrv.Serve(lis)

	clientTLS := &tls.Config{
		InsecureSkipVerify: true,
		MinVersion:         tls.VersionTLS12,
	}
	conn, err := grpc.NewClient(
		lis.Addr().String(),
		grpc.WithTransportCredentials(credentials.NewTLS(clientTLS)),
	)
	if err != nil {
		grpcSrv.Stop()
		t.Fatalf("dial: %v", err)
	}

	client := pb.NewGNMIClient(conn)

	cleanup := func() {
		conn.Close()
		grpcSrv.Stop()
	}

	return &client, cleanup
}

func generateTestTLSConfig(t *testing.T) *tls.Config {
	t.Helper()

	cert, err := tls.X509KeyPair(testCertPEM, testKeyPEM)
	if err != nil {
		t.Fatalf("load test cert: %v", err)
	}

	return &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS12,
	}
}

func TestCapabilities(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	resp, err := (*client).Capabilities(ctx, &pb.CapabilityRequest{})
	if err != nil {
		t.Fatalf("Capabilities RPC failed: %v", err)
	}

	if resp.GNMIVersion == "" {
		t.Error("GNMIVersion should not be empty")
	}

	if len(resp.SupportedModels) == 0 {
		t.Fatal("SupportedModels should not be empty")
	}

	foundOC := false
	foundLFT := false
	for _, m := range resp.SupportedModels {
		if m.Name == "openconfig-interfaces" {
			foundOC = true
		}
		if m.Name == "org-lft-extensions" {
			foundLFT = true
		}
	}
	if !foundOC {
		t.Error("openconfig-interfaces model not in capabilities")
	}
	if !foundLFT {
		t.Error("org-lft-extensions model not in capabilities")
	}

	if len(resp.SupportedEncodings) == 0 {
		t.Error("SupportedEncodings should not be empty")
	}
}

func TestGet_AllInterfaces(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	resp, err := (*client).Get(ctx, &pb.GetRequest{
		Path: []*pb.Path{
			gnmiPath(
				pathElem("interfaces", nil),
				pathElem("interface", map[string]string{"name": "eth0"}),
			),
		},
	})
	if err != nil {
		t.Fatalf("Get RPC failed: %v", err)
	}

	if len(resp.Notification) == 0 {
		t.Fatal("Get response should have notifications")
	}

	notif := resp.Notification[0]
	if len(notif.Update) == 0 {
		t.Fatal("Get response should have updates")
	}

	if len(notif.Update) < 13 {
		t.Errorf("expected at least 13 updates for eth0, got %d", len(notif.Update))
	}
}

func TestGet_SpecificPath_OperStatus(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	resp, err := (*client).Get(ctx, &pb.GetRequest{
		Path: []*pb.Path{
			gnmiPath(
				pathElem("interfaces", nil),
				pathElem("interface", map[string]string{"name": "eth0"}),
				pathElem("state", nil),
				pathElem("oper-status", nil),
			),
		},
	})
	if err != nil {
		t.Fatalf("Get RPC failed: %v", err)
	}

	notif := resp.Notification[0]
	if len(notif.Update) != 1 {
		t.Fatalf("expected exactly 1 update, got %d", len(notif.Update))
	}

	val, ok := notif.Update[0].Val.Value.(*pb.TypedValue_StringVal)
	if !ok {
		t.Fatalf("expected string value, got %T", notif.Update[0].Val.Value)
	}
	if val.StringVal != "UP" {
		t.Errorf("expected oper-status UP, got %s", val.StringVal)
	}
}

func TestGet_SpecificPath_Counter(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	resp, err := (*client).Get(ctx, &pb.GetRequest{
		Path: []*pb.Path{
			gnmiPath(
				pathElem("interfaces", nil),
				pathElem("interface", map[string]string{"name": "eth0"}),
				pathElem("state", nil),
				pathElem("counters", nil),
				pathElem("in-octets", nil),
			),
		},
	})
	if err != nil {
		t.Fatalf("Get RPC failed: %v", err)
	}

	notif := resp.Notification[0]
	if len(notif.Update) != 1 {
		t.Fatalf("expected exactly 1 update, got %d", len(notif.Update))
	}

	val, ok := notif.Update[0].Val.Value.(*pb.TypedValue_UintVal)
	if !ok {
		t.Fatalf("expected uint value, got %T", notif.Update[0].Val.Value)
	}
	if val.UintVal != 1000 {
		t.Errorf("expected in-octets 1000, got %d", val.UintVal)
	}
}

func TestGet_AllCounters(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	resp, err := (*client).Get(ctx, &pb.GetRequest{
		Path: []*pb.Path{
			gnmiPath(
				pathElem("interfaces", nil),
				pathElem("interface", map[string]string{"name": "eth0"}),
				pathElem("state", nil),
				pathElem("counters", nil),
			),
		},
	})
	if err != nil {
		t.Fatalf("Get RPC failed: %v", err)
	}

	notif := resp.Notification[0]
	if len(notif.Update) != 9 {
		t.Errorf("expected 9 counter updates, got %d", len(notif.Update))
	}
}

func TestGet_NonExistentInterface(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	resp, err := (*client).Get(ctx, &pb.GetRequest{
		Path: []*pb.Path{
			gnmiPath(
				pathElem("interfaces", nil),
				pathElem("interface", map[string]string{"name": "nonexistent"}),
				pathElem("state", nil),
				pathElem("oper-status", nil),
			),
		},
	})
	if err != nil {
		t.Fatalf("Get RPC failed: %v", err)
	}

	notif := resp.Notification[0]
	if len(notif.Update) != 0 {
		t.Errorf("expected 0 updates for nonexistent interface, got %d", len(notif.Update))
	}
}

func TestGet_MultiplePaths(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	resp, err := (*client).Get(ctx, &pb.GetRequest{
		Path: []*pb.Path{
			gnmiPath(
				pathElem("interfaces", nil),
				pathElem("interface", map[string]string{"name": "eth0"}),
				pathElem("state", nil),
				pathElem("oper-status", nil),
			),
			gnmiPath(
				pathElem("interfaces", nil),
				pathElem("interface", map[string]string{"name": "eth0"}),
				pathElem("state", nil),
				pathElem("counters", nil),
				pathElem("in-octets", nil),
			),
		},
	})
	if err != nil {
		t.Fatalf("Get RPC failed: %v", err)
	}

	notif := resp.Notification[0]
	if len(notif.Update) != 2 {
		t.Errorf("expected 2 updates for 2 specific paths, got %d", len(notif.Update))
	}
}

func TestGet_WithPrefix(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	resp, err := (*client).Get(ctx, &pb.GetRequest{
		Prefix: gnmiPath(
			pathElem("interfaces", nil),
			pathElem("interface", map[string]string{"name": "eth0"}),
			pathElem("state", nil),
		),
		Path: []*pb.Path{
			gnmiPath(pathElem("oper-status", nil)),
		},
	})
	if err != nil {
		t.Fatalf("Get RPC failed: %v", err)
	}

	notif := resp.Notification[0]
	if len(notif.Update) != 1 {
		t.Fatalf("expected 1 update with prefix, got %d", len(notif.Update))
	}

	val, ok := notif.Update[0].Val.Value.(*pb.TypedValue_StringVal)
	if !ok {
		t.Fatalf("expected string value, got %T", notif.Update[0].Val.Value)
	}
	if val.StringVal != "UP" {
		t.Errorf("expected oper-status UP, got %s", val.StringVal)
	}
}

func TestGet_EmptyPath(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := (*client).Get(ctx, &pb.GetRequest{
		Path: []*pb.Path{},
	})
	if err == nil {
		t.Error("Get with empty path should return error")
	}
}

func TestSubscribe_Once_InitialSync(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	stream, err := (*client).Subscribe(ctx)
	if err != nil {
		t.Fatalf("Subscribe stream open failed: %v", err)
	}

	err = stream.Send(&pb.SubscribeRequest{
		Request: &pb.SubscribeRequest_Subscribe{
			Subscribe: &pb.SubscriptionList{
				Mode: pb.SubscriptionList_ONCE,
				Subscription: []*pb.Subscription{
					{
						Path: gnmiPath(
							pathElem("interfaces", nil),
							pathElem("interface", map[string]string{"name": "eth0"}),
							pathElem("state", nil),
							pathElem("oper-status", nil),
						),
						Mode: pb.SubscriptionMode_ON_CHANGE,
					},
				},
			},
		},
	})
	if err != nil {
		t.Fatalf("Send subscribe request failed: %v", err)
	}

	var gotUpdate bool
	var gotSync bool

	for !gotUpdate || !gotSync {
		resp, err := stream.Recv()
		if err != nil {
			t.Fatalf("Recv failed: %v", err)
		}

		if u := resp.GetUpdate(); u != nil {
			gotUpdate = true
			if len(u.Update) != 1 {
				t.Errorf("expected 1 update in initial sync, got %d", len(u.Update))
			}
		}

		if resp.GetSyncResponse() {
			gotSync = true
		}
	}

	if !gotUpdate {
		t.Error("did not receive initial update")
	}
	if !gotSync {
		t.Error("did not receive sync_response")
	}
}

func TestSubscribe_Poll(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	stream, err := (*client).Subscribe(ctx)
	if err != nil {
		t.Fatalf("Subscribe stream open failed: %v", err)
	}

	err = stream.Send(&pb.SubscribeRequest{
		Request: &pb.SubscribeRequest_Subscribe{
			Subscribe: &pb.SubscriptionList{
				Mode: pb.SubscriptionList_POLL,
				Subscription: []*pb.Subscription{
					{
						Path: gnmiPath(
							pathElem("interfaces", nil),
							pathElem("interface", map[string]string{"name": "eth0"}),
							pathElem("state", nil),
							pathElem("oper-status", nil),
						),
						Mode: pb.SubscriptionMode_ON_CHANGE,
					},
				},
			},
		},
	})
	if err != nil {
		t.Fatalf("Send subscribe request failed: %v", err)
	}

	for {
		resp, err := stream.Recv()
		if err != nil {
			t.Fatalf("Recv failed during initial sync: %v", err)
		}
		if resp.GetSyncResponse() {
			break
		}
	}

	err = stream.Send(&pb.SubscribeRequest{
		Request: &pb.SubscribeRequest_Poll{
			Poll: &pb.Poll{},
		},
	})
	if err != nil {
		t.Fatalf("Send poll failed: %v", err)
	}

	var gotUpdate bool
	for !gotUpdate {
		resp, err := stream.Recv()
		if err != nil {
			t.Fatalf("Recv failed after poll: %v", err)
		}
		if u := resp.GetUpdate(); u != nil && len(u.Update) > 0 {
			gotUpdate = true
		}
	}
}

func TestSubscribe_Sample(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	stream, err := (*client).Subscribe(ctx)
	if err != nil {
		t.Fatalf("Subscribe stream open failed: %v", err)
	}

	err = stream.Send(&pb.SubscribeRequest{
		Request: &pb.SubscribeRequest_Subscribe{
			Subscribe: &pb.SubscriptionList{
				Mode: pb.SubscriptionList_STREAM,
				Subscription: []*pb.Subscription{
					{
						Path: gnmiPath(
							pathElem("interfaces", nil),
							pathElem("interface", map[string]string{"name": "eth0"}),
							pathElem("state", nil),
							pathElem("counters", nil),
							pathElem("in-octets", nil),
						),
						Mode:          pb.SubscriptionMode_SAMPLE,
						SampleInterval: 100_000_000,
					},
				},
			},
		},
	})
	if err != nil {
		t.Fatalf("Send subscribe request failed: %v", err)
	}

	var gotSync bool
	var gotSampleUpdate bool
	deadline := time.After(3 * time.Second)

	for !gotSync || !gotSampleUpdate {
		select {
		case <-deadline:
			t.Fatalf("timeout: gotSync=%v gotSampleUpdate=%v", gotSync, gotSampleUpdate)
		default:
		}

		resp, err := stream.Recv()
		if err != nil {
			t.Fatalf("Recv failed: %v", err)
		}

		if resp.GetSyncResponse() {
			gotSync = true
		}
		if u := resp.GetUpdate(); u != nil {
			if gotSync && len(u.Update) > 0 {
				gotSampleUpdate = true
			}
		}
	}
}

func TestSet_Unimplemented(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := (*client).Set(ctx, &pb.SetRequest{})
	if err == nil {
		t.Error("Set should return error (unimplemented)")
	}
}
