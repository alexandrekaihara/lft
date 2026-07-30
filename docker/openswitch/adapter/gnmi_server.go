package main

import (
	"context"
	"log"
	"time"

	pb "github.com/openconfig/gnmi/proto/gnmi"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type OVSDBProvider interface {
	ListInterfaces() ([]OVSDBInterface, error)
	ListPorts() ([]OVSDBPort, error)
	ListBridges() ([]OVSDBBridge, error)
	Subscribe() chan OVSDBChangeEvent
	Unsubscribe(ch chan OVSDBChangeEvent)
}

type GNMIServer struct {
	pb.UnimplementedGNMIServer
	ovsdb    OVSDBProvider
	rateCalc *CounterRate
	prober   *LatencyProber
}

func NewGNMIServer(ovsdb OVSDBProvider, rateCalc *CounterRate, prober *LatencyProber) *GNMIServer {
	return &GNMIServer{
		ovsdb:    ovsdb,
		rateCalc: rateCalc,
		prober:   prober,
	}
}

func (s *GNMIServer) Capabilities(ctx context.Context, req *pb.CapabilityRequest) (*pb.CapabilityResponse, error) {
	return &pb.CapabilityResponse{
		GNMIVersion: "0.7.0",
		SupportedModels: []*pb.ModelData{
			{Name: "openconfig-interfaces", Organization: "OpenConfig working group", Version: "2.4.0"},
			{Name: "org-lft-extensions", Organization: "profissa/lft", Version: "0.1.0"},
		},
		SupportedEncodings: []pb.Encoding{
			pb.Encoding_JSON,
			pb.Encoding_PROTO,
		},
	}, nil
}

func (s *GNMIServer) Get(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
	if len(req.Path) == 0 {
		return nil, status.Errorf(codes.InvalidArgument, "Get: at least one path required")
	}

	allUpdates, err := s.collectAllUpdates()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "Get: failed to read OVSDB: %v", err)
	}

	var notificationUpdates []*pb.Update
	for _, queryPath := range req.Path {
		fullPath := joinPaths(req.Prefix, queryPath)
		matched := FilterUpdates(allUpdates, fullPath)
		notificationUpdates = append(notificationUpdates, matched...)
	}

	notification := &pb.Notification{
		Timestamp: time.Now().UnixNano(),
		Prefix:    req.Prefix,
		Update:    notificationUpdates,
	}

	return &pb.GetResponse{Notification: []*pb.Notification{notification}}, nil
}

func (s *GNMIServer) collectAllUpdates() ([]*pb.Update, error) {
	interfaces, err := s.ovsdb.ListInterfaces()
	if err != nil {
		return nil, err
	}

	ports, err := s.ovsdb.ListPorts()
	if err != nil {
		return nil, err
	}

	bridges, err := s.ovsdb.ListBridges()
	if err != nil {
		return nil, err
	}

	bridgePortUUIDs := make(map[string]bool)
	for _, br := range bridges {
		for _, portUUID := range br.Ports {
			bridgePortUUIDs[portUUID] = true
		}
	}

	portInterfaceUUIDs := make(map[string]bool)
	for _, port := range ports {
		for _, ifaceUUID := range port.Interfaces {
			portInterfaceUUIDs[ifaceUUID] = true
		}
	}

	onBridge := make(map[string]bool)
	for _, port := range ports {
		if bridgePortUUIDs[port.UUID] {
			for _, ifaceUUID := range port.Interfaces {
				onBridge[ifaceUUID] = true
			}
		}
	}

	var allUpdates []*pb.Update
	for _, iface := range interfaces {
		translated := TranslateInterface(iface, onBridge)
		allUpdates = append(allUpdates, translated.Updates...)

		rateUpdates := TranslateInterfaceRates(iface, s.rateCalc)
		allUpdates = append(allUpdates, rateUpdates...)
	}

	if s.prober != nil && s.prober.Enabled() {
		for ip, stats := range s.prober.AllStats() {
			allUpdates = append(allUpdates, TranslateLatencyResult(ip, stats.RTTNS, stats.AvgNS, stats.MaxNS, stats.MinNS)...)
		}
	}

	return allUpdates, nil
}

func joinPaths(prefix, path *pb.Path) *pb.Path {
	if prefix == nil || len(prefix.Elem) == 0 {
		return path
	}
	if path == nil {
		return prefix
	}
	joined := &pb.Path{
		Elem:   make([]*pb.PathElem, 0, len(prefix.Elem)+len(path.Elem)),
		Origin: prefix.Origin,
		Target: prefix.Target,
	}
	joined.Elem = append(joined.Elem, prefix.Elem...)
	joined.Elem = append(joined.Elem, path.Elem...)
	return joined
}

func (s *GNMIServer) Set(ctx context.Context, req *pb.SetRequest) (*pb.SetResponse, error) {
	return nil, status.Errorf(codes.Unimplemented, "Set RPC not supported (read-only adapter)")
}

func (s *GNMIServer) Subscribe(stream pb.GNMI_SubscribeServer) error {
	ctx := stream.Context()

	firstReq, err := stream.Recv()
	if err != nil {
		return err
	}

	subList := firstReq.GetSubscribe()
	if subList == nil {
		return status.Errorf(codes.InvalidArgument, "Subscribe: first request must be a SubscriptionList")
	}

	subPaths := make([]*pb.Path, 0, len(subList.Subscription))
	subModes := make(map[int]pb.SubscriptionMode, len(subList.Subscription))
	sampleIntervals := make(map[int]uint64, len(subList.Subscription))
	for i, sub := range subList.Subscription {
		fullPath := joinPaths(subList.Prefix, sub.Path)
		subPaths = append(subPaths, fullPath)
		subModes[i] = sub.Mode
		sampleIntervals[i] = sub.SampleInterval
	}

	hasOnChange := false
	hasSample := false
	for _, mode := range subModes {
		switch mode {
		case pb.SubscriptionMode_ON_CHANGE:
			hasOnChange = true
		case pb.SubscriptionMode_SAMPLE:
			hasSample = true
		case pb.SubscriptionMode_TARGET_DEFINED:
			hasOnChange = true
		}
	}

	if !subList.UpdatesOnly {
		if err := s.sendInitialSync(stream, ctx, subList, subPaths); err != nil {
			return err
		}
	}

	switch subList.Mode {
	case pb.SubscriptionList_ONCE:
		return nil

	case pb.SubscriptionList_POLL:
		return s.runPollMode(stream, ctx, subList, subPaths)

	case pb.SubscriptionList_STREAM:
		return s.runStreamMode(stream, ctx, subList, subPaths, subModes, sampleIntervals, hasOnChange, hasSample)

	default:
		return status.Errorf(codes.InvalidArgument, "Subscribe: unsupported subscription list mode %v", subList.Mode)
	}
}

func (s *GNMIServer) sendInitialSync(stream pb.GNMI_SubscribeServer, ctx context.Context, subList *pb.SubscriptionList, subPaths []*pb.Path) error {
	allUpdates, err := s.collectAllUpdates()
	if err != nil {
		return status.Errorf(codes.Internal, "Subscribe: initial sync failed: %v", err)
	}

	var updates []*pb.Update
	for _, subPath := range subPaths {
		updates = append(updates, FilterUpdates(allUpdates, subPath)...)
	}

	if len(updates) > 0 {
		notif := &pb.Notification{
			Timestamp: time.Now().UnixNano(),
			Prefix:    subList.Prefix,
			Update:    updates,
		}
		if err := stream.Send(&pb.SubscribeResponse{
			Response: &pb.SubscribeResponse_Update{Update: notif},
		}); err != nil {
			return err
		}
	}

	return stream.Send(&pb.SubscribeResponse{
		Response: &pb.SubscribeResponse_SyncResponse{SyncResponse: true},
	})
}

func (s *GNMIServer) runPollMode(stream pb.GNMI_SubscribeServer, ctx context.Context, subList *pb.SubscriptionList, subPaths []*pb.Path) error {
	for {
		req, err := stream.Recv()
		if err != nil {
			return err
		}
		if req.GetPoll() == nil {
			continue
		}

		allUpdates, err := s.collectAllUpdates()
		if err != nil {
			return status.Errorf(codes.Internal, "Subscribe POLL: %v", err)
		}

		var updates []*pb.Update
		for _, subPath := range subPaths {
			updates = append(updates, FilterUpdates(allUpdates, subPath)...)
		}

		notif := &pb.Notification{
			Timestamp: time.Now().UnixNano(),
			Prefix:    subList.Prefix,
			Update:    updates,
		}
		if err := stream.Send(&pb.SubscribeResponse{
			Response: &pb.SubscribeResponse_Update{Update: notif},
		}); err != nil {
			return err
		}
	}
}

func (s *GNMIServer) runStreamMode(
	stream pb.GNMI_SubscribeServer,
	ctx context.Context,
	subList *pb.SubscriptionList,
	subPaths []*pb.Path,
	subModes map[int]pb.SubscriptionMode,
	sampleIntervals map[int]uint64,
	hasOnChange, hasSample bool,
) error {
	errCh := make(chan error, 2)

	if hasOnChange {
		go s.streamOnChange(ctx, stream, subList, subPaths, errCh)
	}

	if hasSample {
		go s.streamSample(ctx, stream, subList, subPaths, subModes, sampleIntervals, errCh)
	}

	select {
	case <-ctx.Done():
		return ctx.Err()
	case err := <-errCh:
		return err
	}
}

func (s *GNMIServer) streamOnChange(
	ctx context.Context,
	stream pb.GNMI_SubscribeServer,
	subList *pb.SubscriptionList,
	subPaths []*pb.Path,
	errCh chan<- error,
) {
	eventCh := s.ovsdb.Subscribe()
	defer s.ovsdb.Unsubscribe(eventCh)

	for {
		select {
		case <-ctx.Done():
			errCh <- ctx.Err()
			return
		case evt, ok := <-eventCh:
			if !ok {
				errCh <- status.Errorf(codes.Internal, "OVSDB event channel closed")
				return
			}

			updates := s.translateChangeEvent(evt, subPaths)
			if len(updates) == 0 {
				continue
			}

			notif := &pb.Notification{
				Timestamp: time.Now().UnixNano(),
				Prefix:    subList.Prefix,
				Update:    updates,
			}
			if err := stream.Send(&pb.SubscribeResponse{
				Response: &pb.SubscribeResponse_Update{Update: notif},
			}); err != nil {
				errCh <- err
				return
			}
		}
	}
}

func (s *GNMIServer) translateChangeEvent(evt OVSDBChangeEvent, subPaths []*pb.Path) []*pb.Update {
	var updates []*pb.Update

	switch evt.Table {
	case "Interface":
		if evt.Op == "delete" {
			if iface, ok := evt.Old.(*OVSDBInterface); ok {
				translated := TranslateInterface(*iface, nil)
				for _, u := range translated.Updates {
					for _, subPath := range subPaths {
						if PathMatches(subPath, u.Path) {
							updates = append(updates, &pb.Update{
								Path: u.Path,
							})
							break
						}
					}
				}
			}
			return updates
		}

		var iface *OVSDBInterface
		if evt.Op == "add" {
			iface, _ = evt.New.(*OVSDBInterface)
		} else {
			iface, _ = evt.New.(*OVSDBInterface)
		}
		if iface == nil {
			return nil
		}

		onBridge, err := s.resolveOnBridge()
		if err != nil {
			log.Printf("subscribe: on_change: failed to resolve onBridge: %v", err)
			onBridge = nil
		}

		translated := TranslateInterface(*iface, onBridge)
		rateUpdates := TranslateInterfaceRates(*iface, s.rateCalc)
		allUpdates := append(translated.Updates, rateUpdates...)

		for _, u := range allUpdates {
			for _, subPath := range subPaths {
				if PathMatches(subPath, u.Path) {
					updates = append(updates, u)
					break
				}
			}
		}

	case "Port", "Bridge":
		allUpdates, err := s.collectAllUpdates()
		if err != nil {
			log.Printf("subscribe: on_change: failed to collect updates: %v", err)
			return nil
		}
		for _, u := range allUpdates {
			for _, subPath := range subPaths {
				if PathMatches(subPath, u.Path) {
					updates = append(updates, u)
					break
				}
			}
		}
	}

	return updates
}

func (s *GNMIServer) streamSample(
	ctx context.Context,
	stream pb.GNMI_SubscribeServer,
	subList *pb.SubscriptionList,
	subPaths []*pb.Path,
	subModes map[int]pb.SubscriptionMode,
	sampleIntervals map[int]uint64,
	errCh chan<- error,
) {
	minInterval := uint64(0)
	for i, mode := range subModes {
		if mode != pb.SubscriptionMode_SAMPLE {
			continue
		}
		interval := sampleIntervals[i]
		if interval == 0 {
			interval = 10_000_000_000
		}
		if minInterval == 0 || interval < minInterval {
			minInterval = interval
		}
	}
	if minInterval == 0 {
		minInterval = 10_000_000_000
	}

	ticker := time.NewTicker(time.Duration(minInterval) * time.Nanosecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			errCh <- ctx.Err()
			return
		case <-ticker.C:
			allUpdates, err := s.collectAllUpdates()
			if err != nil {
				log.Printf("subscribe: sample: failed to collect updates: %v", err)
				continue
			}

			var updates []*pb.Update
			for i, subPath := range subPaths {
				if subModes[i] != pb.SubscriptionMode_SAMPLE {
					continue
				}
				updates = append(updates, FilterUpdates(allUpdates, subPath)...)
			}

			if len(updates) == 0 {
				continue
			}

			notif := &pb.Notification{
				Timestamp: time.Now().UnixNano(),
				Prefix:    subList.Prefix,
				Update:    updates,
			}
			if err := stream.Send(&pb.SubscribeResponse{
				Response: &pb.SubscribeResponse_Update{Update: notif},
			}); err != nil {
				errCh <- err
				return
			}
		}
	}
}

func (s *GNMIServer) resolveOnBridge() (map[string]bool, error) {
	ports, err := s.ovsdb.ListPorts()
	if err != nil {
		return nil, err
	}
	bridges, err := s.ovsdb.ListBridges()
	if err != nil {
		return nil, err
	}

	bridgePortUUIDs := make(map[string]bool)
	for _, br := range bridges {
		for _, portUUID := range br.Ports {
			bridgePortUUIDs[portUUID] = true
		}
	}

	onBridge := make(map[string]bool)
	for _, port := range ports {
		if bridgePortUUIDs[port.UUID] {
			for _, ifaceUUID := range port.Interfaces {
				onBridge[ifaceUUID] = true
			}
		}
	}
	return onBridge, nil
}
