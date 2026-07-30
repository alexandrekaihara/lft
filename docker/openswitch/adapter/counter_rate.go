package main

import (
	"sync"
	"time"
)

type sample struct {
	ts    time.Time
	value uint64
}

type CounterRate struct {
	mu      sync.RWMutex
	window  int
	samples map[string][]sample
}

func NewCounterRate(windowSize int) *CounterRate {
	if windowSize < 2 {
		windowSize = 2
	}
	return &CounterRate{
		window:  windowSize,
		samples: make(map[string][]sample),
	}
}

func (c *CounterRate) key(iface, counter string) string {
	return iface + ":" + counter
}

func (c *CounterRate) Record(iface, counter string, value uint64) {
	k := c.key(iface, counter)
	now := time.Now()

	c.mu.Lock()
	defer c.mu.Unlock()

	s := c.samples[k]
	s = append(s, sample{ts: now, value: value})

	if len(s) > c.window {
		s = s[len(s)-c.window:]
	}
	c.samples[k] = s
}

func (c *CounterRate) Rate(iface, counter string) (float64, bool) {
	k := c.key(iface, counter)

	c.mu.RLock()
	defer c.mu.RUnlock()

	s := c.samples[k]
	if len(s) < 2 {
		return 0, false
	}

	oldest := s[0]
	newest := s[len(s)-1]

	dt := newest.ts.Sub(oldest.ts).Seconds()
	if dt <= 0 {
		return 0, false
	}

	dv := newest.value - oldest.value
	if newest.value < oldest.value {
		dv = newest.value
	}

	return float64(dv) / dt, true
}

func (c *CounterRate) RecordInterfaceStats(iface string, stats map[string]int) {
	if stats == nil {
		return
	}
	counters := []string{"rx_bytes", "tx_bytes", "rx_packets", "tx_packets"}
	for _, cn := range counters {
		if v, ok := stats[cn]; ok {
			c.Record(iface, cn, uint64(v))
		}
	}
}
