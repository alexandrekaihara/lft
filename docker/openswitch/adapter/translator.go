package main

import (
	"fmt"
	"strings"

	pb "github.com/openconfig/gnmi/proto/gnmi"
)

func pathElem(name string, key map[string]string) *pb.PathElem {
	return &pb.PathElem{Name: name, Key: key}
}

func gnmiPath(elems ...*pb.PathElem) *pb.Path {
	return &pb.Path{Elem: elems}
}

func uintVal(v uint64) *pb.TypedValue {
	return &pb.TypedValue{Value: &pb.TypedValue_UintVal{UintVal: v}}
}

func intVal(v int64) *pb.TypedValue {
	return &pb.TypedValue{Value: &pb.TypedValue_IntVal{IntVal: v}}
}

func floatVal(v float64) *pb.TypedValue {
	return &pb.TypedValue{Value: &pb.TypedValue_DoubleVal{DoubleVal: v}}
}

func stringVal(v string) *pb.TypedValue {
	return &pb.TypedValue{Value: &pb.TypedValue_StringVal{StringVal: v}}
}

func gnmiUpdate(path *pb.Path, val *pb.TypedValue) *pb.Update {
	return &pb.Update{Path: path, Val: val}
}

func copyElems(elems []*pb.PathElem) []*pb.PathElem {
	c := make([]*pb.PathElem, len(elems))
	copy(c, elems)
	return c
}

func appendElem(elems []*pb.PathElem, name string) []*pb.PathElem {
	return append(copyElems(elems), pathElem(name, nil))
}

type InterfaceUpdates struct {
	Updates []*pb.Update
	Name    string
}

func TranslateInterface(iface OVSDBInterface, bridgePortNames map[string]bool) *InterfaceUpdates {
	result := &InterfaceUpdates{Name: iface.Name}
	n := iface.Name

	ifacePath := []*pb.PathElem{
		pathElem("interfaces", nil),
		pathElem("interface", map[string]string{"name": n}),
		pathElem("state", nil),
	}

	result.Updates = append(result.Updates,
		gnmiUpdate(gnmiPath(appendElem(ifacePath, "name")...), stringVal(n)),
		gnmiUpdate(gnmiPath(appendElem(ifacePath, "type")...), stringVal(translateIfaceType(iface.Type))),
		gnmiUpdate(gnmiPath(appendElem(ifacePath, "oper-status")...), stringVal(translateOperStatus(iface.LinkState))),
		gnmiUpdate(gnmiPath(appendElem(ifacePath, "admin-status")...), stringVal(translateAdminStatus(iface.AdminState, bridgePortNames[iface.UUID]))),
	)

	countersPath := append(ifacePath, pathElem("counters", nil))

	statMap := iface.Statistics
	if statMap == nil {
		statMap = map[string]int{}
	}

	result.Updates = append(result.Updates,
		gnmiUpdate(gnmiPath(appendElem(countersPath, "in-octets")...), uintVal(uint64(statMap["rx_bytes"]))),
		gnmiUpdate(gnmiPath(appendElem(countersPath, "out-octets")...), uintVal(uint64(statMap["tx_bytes"]))),
		gnmiUpdate(gnmiPath(appendElem(countersPath, "in-unicast-pkts")...), uintVal(uint64(statMap["rx_packets"]))),
		gnmiUpdate(gnmiPath(appendElem(countersPath, "out-unicast-pkts")...), uintVal(uint64(statMap["tx_packets"]))),
		gnmiUpdate(gnmiPath(appendElem(countersPath, "in-discards")...), uintVal(uint64(statMap["rx_dropped"]))),
		gnmiUpdate(gnmiPath(appendElem(countersPath, "out-discards")...), uintVal(uint64(statMap["tx_dropped"]))),
		gnmiUpdate(gnmiPath(appendElem(countersPath, "in-errors")...), uintVal(uint64(statMap["rx_errors"]))),
		gnmiUpdate(gnmiPath(appendElem(countersPath, "out-errors")...), uintVal(uint64(statMap["tx_errors"]))),
		gnmiUpdate(gnmiPath(appendElem(countersPath, "in-fcs-errors")...), uintVal(uint64(statMap["rx_crc_err"]))),
	)

	return result
}

func TranslateInterfaceRates(iface OVSDBInterface, rateCalc *CounterRate) []*pb.Update {
	n := iface.Name
	var updates []*pb.Update

	ratePath := []*pb.PathElem{
		pathElem("org-lft", nil),
		pathElem("interfaces", nil),
		pathElem("interface", map[string]string{"name": n}),
		pathElem("state", nil),
		pathElem("rate", nil),
	}

	if r, ok := rateCalc.Rate(n, "rx_bytes"); ok {
		updates = append(updates, gnmiUpdate(gnmiPath(appendElem(ratePath, "in-octets")...), floatVal(r)))
	}
	if r, ok := rateCalc.Rate(n, "tx_bytes"); ok {
		updates = append(updates, gnmiUpdate(gnmiPath(appendElem(ratePath, "out-octets")...), floatVal(r)))
	}
	if r, ok := rateCalc.Rate(n, "rx_packets"); ok {
		updates = append(updates, gnmiUpdate(gnmiPath(appendElem(ratePath, "in-pkts")...), floatVal(r)))
	}
	if r, ok := rateCalc.Rate(n, "tx_packets"); ok {
		updates = append(updates, gnmiUpdate(gnmiPath(appendElem(ratePath, "out-pkts")...), floatVal(r)))
	}

	return updates
}

func TranslateLatencyResult(ip string, rttNS uint64, avgNS, maxNS, minNS uint64) []*pb.Update {
	targetPath := []*pb.PathElem{
		pathElem("org-lft", nil),
		pathElem("latency", nil),
		pathElem("target", map[string]string{"ip": ip}),
		pathElem("state", nil),
	}

	return []*pb.Update{
		gnmiUpdate(gnmiPath(appendElem(targetPath, "rtt-ns")...), uintVal(rttNS)),
		gnmiUpdate(gnmiPath(appendElem(targetPath, "rtt-avg-ns")...), uintVal(avgNS)),
		gnmiUpdate(gnmiPath(appendElem(targetPath, "rtt-max-ns")...), uintVal(maxNS)),
		gnmiUpdate(gnmiPath(appendElem(targetPath, "rtt-min-ns")...), uintVal(minNS)),
	}
}

func translateOperStatus(linkState *string) string {
	if linkState == nil {
		return "DOWN"
	}
	switch strings.ToLower(*linkState) {
	case "up":
		return "UP"
	case "down":
		return "DOWN"
	default:
		return "DOWN"
	}
}

func translateAdminStatus(adminState *string, onBridge bool) string {
	if adminState != nil && strings.ToLower(*adminState) == "down" {
		return "DOWN"
	}
	if onBridge {
		return "UP"
	}
	return "DOWN"
}

func translateIfaceType(t string) string {
	switch t {
	case "":
		return "ethernetCsmacd"
	case "internal":
		return "softwareLoopback"
	case "gre":
		return "tunnelGre"
	case "vxlan":
		return "ianaiftVxlan"
	case "geneve":
		return "ianaiftGeneve"
	default:
		return t
	}
}

func PathMatches(query *pb.Path, candidate *pb.Path) bool {
	if query == nil || len(query.Elem) == 0 {
		return true
	}
	if len(query.Elem) > len(candidate.Elem) {
		return false
	}
	for i, qe := range query.Elem {
		ce := candidate.Elem[i]
		if qe.Name != ce.Name {
			return false
		}
		for k, v := range qe.Key {
			cv, ok := ce.Key[k]
			if !ok || cv != v {
				return false
			}
		}
	}
	return true
}

func PathToString(p *pb.Path) string {
	if p == nil {
		return "/"
	}
	var sb strings.Builder
	for _, e := range p.Elem {
		sb.WriteString("/")
		sb.WriteString(e.Name)
		if len(e.Key) > 0 {
			sb.WriteString("[")
			first := true
			for k, v := range e.Key {
				if !first {
					sb.WriteString(",")
				}
				sb.WriteString(fmt.Sprintf("%s=%s", k, v))
				first = false
			}
			sb.WriteString("]")
		}
	}
	return sb.String()
}

func FilterUpdates(updates []*pb.Update, query *pb.Path) []*pb.Update {
	if query == nil || len(query.Elem) == 0 {
		return updates
	}
	var result []*pb.Update
	for _, u := range updates {
		if PathMatches(query, u.Path) {
			result = append(result, u)
		}
	}
	return result
}
