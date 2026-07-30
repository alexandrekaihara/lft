package main

import (
	"testing"
	"time"
)

func TestCounterRate_NeedsTwoSamples(t *testing.T) {
	rc := NewCounterRate(5)

	_, ok := rc.Rate("eth0", "rx_bytes")
	if ok {
		t.Error("Rate should return false with no samples")
	}

	rc.Record("eth0", "rx_bytes", 1000)
	_, ok = rc.Rate("eth0", "rx_bytes")
	if ok {
		t.Error("Rate should return false with only one sample")
	}
}

func TestCounterRate_BasicRate(t *testing.T) {
	rc := NewCounterRate(5)

	rc.Record("eth0", "rx_bytes", 1000)
	time.Sleep(10 * time.Millisecond)
	rc.Record("eth0", "rx_bytes", 2000)

	rate, ok := rc.Rate("eth0", "rx_bytes")
	if !ok {
		t.Fatal("Rate should return true with two samples")
	}

	if rate < 50000 || rate > 150000 {
		t.Errorf("expected rate ~100000 bytes/s (1000 bytes in ~0.01s), got %f", rate)
	}
}

func TestCounterRate_MultipleCounters(t *testing.T) {
	rc := NewCounterRate(5)

	rc.Record("eth0", "rx_bytes", 100)
	rc.Record("eth0", "tx_bytes", 200)
	time.Sleep(10 * time.Millisecond)
	rc.Record("eth0", "rx_bytes", 200)
	rc.Record("eth0", "tx_bytes", 400)

	rxRate, ok := rc.Rate("eth0", "rx_bytes")
	if !ok {
		t.Fatal("rx_bytes rate should be available")
	}

	txRate, ok := rc.Rate("eth0", "tx_bytes")
	if !ok {
		t.Fatal("tx_bytes rate should be available")
	}

	if rxRate <= 0 {
		t.Errorf("rx rate should be positive, got %f", rxRate)
	}
	if txRate <= 0 {
		t.Errorf("tx rate should be positive, got %f", txRate)
	}
}

func TestCounterRate_DifferentInterfaces(t *testing.T) {
	rc := NewCounterRate(5)

	rc.Record("eth0", "rx_bytes", 100)
	rc.Record("eth1", "rx_bytes", 200)
	time.Sleep(10 * time.Millisecond)
	rc.Record("eth0", "rx_bytes", 200)
	rc.Record("eth1", "rx_bytes", 400)

	r0, ok0 := rc.Rate("eth0", "rx_bytes")
	r1, ok1 := rc.Rate("eth1", "rx_bytes")

	if !ok0 || !ok1 {
		t.Fatal("both interface rates should be available")
	}
	if r0 <= 0 || r1 <= 0 {
		t.Errorf("rates should be positive: eth0=%f eth1=%f", r0, r1)
	}
}

func TestCounterRate_WindowTrims(t *testing.T) {
	rc := NewCounterRate(3)

	for i := 0; i < 10; i++ {
		rc.Record("eth0", "rx_bytes", uint64(i*100))
		time.Sleep(1 * time.Millisecond)
	}

	rate, ok := rc.Rate("eth0", "rx_bytes")
	if !ok {
		t.Fatal("rate should be available")
	}
	if rate <= 0 {
		t.Errorf("rate should be positive, got %f", rate)
	}
}

func TestCounterRate_Wraparound(t *testing.T) {
	rc := NewCounterRate(5)

	rc.Record("eth0", "rx_bytes", 1000000)
	time.Sleep(10 * time.Millisecond)
	rc.Record("eth0", "rx_bytes", 500)

	rate, ok := rc.Rate("eth0", "rx_bytes")
	if !ok {
		t.Fatal("rate should be available after wraparound")
	}
	if rate < 0 {
		t.Errorf("rate should not be negative after wraparound, got %f", rate)
	}
}

func TestCounterRate_RecordInterfaceStats(t *testing.T) {
	rc := NewCounterRate(5)

	stats := map[string]int{
		"rx_bytes":   1000,
		"tx_bytes":   2000,
		"rx_packets": 10,
		"tx_packets": 20,
		"rx_dropped": 5,
	}

	rc.RecordInterfaceStats("eth0", stats)
	time.Sleep(10 * time.Millisecond)
	rc.RecordInterfaceStats("eth0", stats)

	for _, counter := range []string{"rx_bytes", "tx_bytes", "rx_packets", "tx_packets"} {
		_, ok := rc.Rate("eth0", counter)
		if !ok {
			t.Errorf("rate for %s should be available", counter)
		}
	}

	_, ok := rc.Rate("eth0", "rx_dropped")
	if ok {
		t.Error("rx_dropped should not be tracked (not in the counters list)")
	}
}

func TestCounterRate_RecordInterfaceStats_NilMap(t *testing.T) {
	rc := NewCounterRate(5)
	rc.RecordInterfaceStats("eth0", nil)

	_, ok := rc.Rate("eth0", "rx_bytes")
	if ok {
		t.Error("rate should not be available after nil stats")
	}
}

func TestCounterRate_MinWindowEnforced(t *testing.T) {
	rc := NewCounterRate(1)

	if rc.window < 2 {
		t.Error("window should be at least 2")
	}
}

func TestCounterRate_ZeroTimeDelta(t *testing.T) {
	rc := NewCounterRate(5)

	rc.Record("eth0", "rx_bytes", 1000)
	rc.Record("eth0", "rx_bytes", 2000)

	_, ok := rc.Rate("eth0", "rx_bytes")
	if !ok {
		t.Log("rate with zero time delta returns false — acceptable")
	}
}
