package main

import (
	"testing"

	pb "github.com/openconfig/gnmi/proto/gnmi"
)

func makeTestInterface() OVSDBInterface {
	return OVSDBInterface{
		UUID:       "iface-uuid-1",
		Name:       "eth0",
		Type:       "",
		LinkState:  "up",
		AdminState: "up",
		Ofport:     1,
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
	}
}

func TestTranslateInterface_AllPaths(t *testing.T) {
	iface := makeTestInterface()
	onBridge := map[string]bool{"iface-uuid-1": true}

	result := TranslateInterface(iface, onBridge)

	if result.Name != "eth0" {
		t.Errorf("expected name eth0, got %s", result.Name)
	}

	expectedCount := 13
	if len(result.Updates) != expectedCount {
		t.Fatalf("expected %d updates, got %d", expectedCount, len(result.Updates))
	}

	updatesByPath := make(map[string]*pb.Update)
	for _, u := range result.Updates {
		updatesByPath[PathToString(u.Path)] = u
	}

	assertStringVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/name", "eth0")
	assertStringVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/type", "ethernetCsmacd")
	assertStringVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/oper-status", "UP")
	assertStringVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/admin-status", "UP")

	assertUintVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/counters/in-octets", 1000)
	assertUintVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/counters/out-octets", 2000)
	assertUintVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/counters/in-unicast-pkts", 10)
	assertUintVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/counters/out-unicast-pkts", 20)
	assertUintVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/counters/in-discards", 5)
	assertUintVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/counters/out-discards", 3)
	assertUintVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/counters/in-errors", 1)
	assertUintVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/counters/out-errors", 2)
	assertUintVal(t, updatesByPath, "/interfaces/interface[name=eth0]/state/counters/in-fcs-errors", 4)
}

func TestTranslateInterface_OperStatusMapping(t *testing.T) {
	cases := []struct {
		linkState string
		expected  string
	}{
		{"up", "UP"},
		{"UP", "UP"},
		{"down", "DOWN"},
		{"DOWN", "DOWN"},
		{"", "DOWN"},
		{"unknown", "DOWN"},
	}

	for _, c := range cases {
		got := translateOperStatus(c.linkState)
		if got != c.expected {
			t.Errorf("translateOperStatus(%q) = %q, want %q", c.linkState, got, c.expected)
		}
	}
}

func TestTranslateInterface_AdminStatusMapping(t *testing.T) {
	cases := []struct {
		adminState string
		onBridge   bool
		expected   string
	}{
		{"up", true, "UP"},
		{"up", false, "DOWN"},
		{"down", true, "DOWN"},
		{"", true, "UP"},
		{"", false, "DOWN"},
	}

	for _, c := range cases {
		got := translateAdminStatus(c.adminState, c.onBridge)
		if got != c.expected {
			t.Errorf("translateAdminStatus(%q, %v) = %q, want %q", c.adminState, c.onBridge, got, c.expected)
		}
	}
}

func TestTranslateInterface_TypeMapping(t *testing.T) {
	cases := []struct {
		ovsType  string
		expected string
	}{
		{"", "ethernetCsmacd"},
		{"internal", "softwareLoopback"},
		{"gre", "tunnelGre"},
		{"vxlan", "ianaiftVxlan"},
		{"geneve", "ianaiftGeneve"},
		{"custom-type", "custom-type"},
	}

	for _, c := range cases {
		got := translateIfaceType(c.ovsType)
		if got != c.expected {
			t.Errorf("translateIfaceType(%q) = %q, want %q", c.ovsType, got, c.expected)
		}
	}
}

func TestTranslateInterface_NilStatistics(t *testing.T) {
	iface := OVSDBInterface{
		UUID:       "test",
		Name:       "br0",
		Type:       "internal",
		LinkState:  "down",
		Statistics: nil,
	}

	result := TranslateInterface(iface, nil)

	for _, u := range result.Updates {
		if u.Val == nil {
			continue
		}
		if uv, ok := u.Val.Value.(*pb.TypedValue_UintVal); ok {
			if uv.UintVal != 0 {
				t.Errorf("expected 0 for nil statistics counter at %s, got %d", PathToString(u.Path), uv.UintVal)
			}
		}
	}
}

func TestPathMatches_ExactPath(t *testing.T) {
	query := gnmiPath(
		pathElem("interfaces", nil),
		pathElem("interface", map[string]string{"name": "eth0"}),
		pathElem("state", nil),
		pathElem("oper-status", nil),
	)
	candidate := gnmiPath(
		pathElem("interfaces", nil),
		pathElem("interface", map[string]string{"name": "eth0"}),
		pathElem("state", nil),
		pathElem("oper-status", nil),
	)
	if !PathMatches(query, candidate) {
		t.Error("exact path should match")
	}
}

func TestPathMatches_PrefixPath(t *testing.T) {
	query := gnmiPath(
		pathElem("interfaces", nil),
		pathElem("interface", map[string]string{"name": "eth0"}),
	)
	candidate := gnmiPath(
		pathElem("interfaces", nil),
		pathElem("interface", map[string]string{"name": "eth0"}),
		pathElem("state", nil),
		pathElem("oper-status", nil),
	)
	if !PathMatches(query, candidate) {
		t.Error("prefix path should match longer candidate")
	}
}

func TestPathMatches_DifferentKey(t *testing.T) {
	query := gnmiPath(
		pathElem("interfaces", nil),
		pathElem("interface", map[string]string{"name": "eth0"}),
	)
	candidate := gnmiPath(
		pathElem("interfaces", nil),
		pathElem("interface", map[string]string{"name": "eth1"}),
	)
	if PathMatches(query, candidate) {
		t.Error("different key should not match")
	}
}

func TestPathMatches_DifferentName(t *testing.T) {
	query := gnmiPath(
		pathElem("interfaces", nil),
		pathElem("interface", nil),
	)
	candidate := gnmiPath(
		pathElem("interfaces", nil),
		pathElem("port", nil),
	)
	if PathMatches(query, candidate) {
		t.Error("different elem name should not match")
	}
}

func TestPathMatches_NilQuery(t *testing.T) {
	candidate := gnmiPath(pathElem("interfaces", nil))
	if !PathMatches(nil, candidate) {
		t.Error("nil query should match any candidate")
	}
}

func TestPathMatches_EmptyQuery(t *testing.T) {
	candidate := gnmiPath(pathElem("interfaces", nil))
	if !PathMatches(&pb.Path{}, candidate) {
		t.Error("empty query should match any candidate")
	}
}

func TestPathMatches_QueryLongerThanCandidate(t *testing.T) {
	query := gnmiPath(
		pathElem("a", nil),
		pathElem("b", nil),
		pathElem("c", nil),
	)
	candidate := gnmiPath(
		pathElem("a", nil),
		pathElem("b", nil),
	)
	if PathMatches(query, candidate) {
		t.Error("query longer than candidate should not match")
	}
}

func TestFilterUpdates(t *testing.T) {
	iface := makeTestInterface()
	result := TranslateInterface(iface, map[string]bool{"iface-uuid-1": true})

	query := gnmiPath(
		pathElem("interfaces", nil),
		pathElem("interface", map[string]string{"name": "eth0"}),
		pathElem("state", nil),
		pathElem("counters", nil),
	)

	filtered := FilterUpdates(result.Updates, query)
	if len(filtered) != 9 {
		t.Errorf("expected 9 counter updates, got %d", len(filtered))
	}

	for _, u := range filtered {
		s := PathToString(u.Path)
		if !contains(s, "counters") {
			t.Errorf("filtered update should contain 'counters': %s", s)
		}
	}
}

func TestPathToString(t *testing.T) {
	p := gnmiPath(
		pathElem("interfaces", nil),
		pathElem("interface", map[string]string{"name": "eth0"}),
		pathElem("state", nil),
	)
	got := PathToString(p)
	expected := "/interfaces/interface[name=eth0]/state"
	if got != expected {
		t.Errorf("PathToString = %q, want %q", got, expected)
	}
}

func TestTranslateLatencyResult(t *testing.T) {
	updates := TranslateLatencyResult("10.0.0.1", 5000000, 4500000, 6000000, 3000000)

	if len(updates) != 4 {
		t.Fatalf("expected 4 latency updates, got %d", len(updates))
	}

	updatesByPath := make(map[string]*pb.Update)
	for _, u := range updates {
		updatesByPath[PathToString(u.Path)] = u
	}

	assertUintVal(t, updatesByPath, "/org-lft/latency/target[ip=10.0.0.1]/state/rtt-ns", 5000000)
	assertUintVal(t, updatesByPath, "/org-lft/latency/target[ip=10.0.0.1]/state/rtt-avg-ns", 4500000)
	assertUintVal(t, updatesByPath, "/org-lft/latency/target[ip=10.0.0.1]/state/rtt-max-ns", 6000000)
	assertUintVal(t, updatesByPath, "/org-lft/latency/target[ip=10.0.0.1]/state/rtt-min-ns", 3000000)
}

func assertStringVal(t *testing.T, m map[string]*pb.Update, path, expected string) {
	t.Helper()
	u, ok := m[path]
	if !ok {
		t.Errorf("no update at path %s", path)
		return
	}
	sv, ok := u.Val.Value.(*pb.TypedValue_StringVal)
	if !ok {
		t.Errorf("path %s: expected string value, got %T", path, u.Val.Value)
		return
	}
	if sv.StringVal != expected {
		t.Errorf("path %s: got %q, want %q", path, sv.StringVal, expected)
	}
}

func assertUintVal(t *testing.T, m map[string]*pb.Update, path string, expected uint64) {
	t.Helper()
	u, ok := m[path]
	if !ok {
		t.Errorf("no update at path %s", path)
		return
	}
	uv, ok := u.Val.Value.(*pb.TypedValue_UintVal)
	if !ok {
		t.Errorf("path %s: expected uint value, got %T", path, u.Val.Value)
		return
	}
	if uv.UintVal != expected {
		t.Errorf("path %s: got %d, want %d", path, uv.UintVal, expected)
	}
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || len(s) > 0 && containsStr(s, sub))
}

func containsStr(s, sub string) bool {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
