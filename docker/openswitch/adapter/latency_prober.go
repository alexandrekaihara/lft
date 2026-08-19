package main

import (
	"bytes"
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

type LatencyStats struct {
	RTTNS uint64
	AvgNS uint64
	MaxNS uint64
	MinNS uint64
}

type ringBuffer struct {
	samples []uint64
	head    int
	count   int
	size    int
}

func newRingBuffer(size int) *ringBuffer {
	return &ringBuffer{
		samples: make([]uint64, size),
		size:    size,
	}
}

func (r *ringBuffer) push(v uint64) {
	r.samples[r.head] = v
	r.head = (r.head + 1) % r.size
	if r.count < r.size {
		r.count++
	}
}

func (r *ringBuffer) stats() (last, avg, max, min uint64, ok bool) {
	if r.count == 0 {
		return 0, 0, 0, 0, false
	}

	lastIdx := (r.head - 1 + r.size) % r.size
	last = r.samples[lastIdx]

	var sum uint64
	max = 0
	min = ^uint64(0)

	for i := 0; i < r.count; i++ {
		v := r.samples[i]
		sum += v
		if v > max {
			max = v
		}
		if v < min {
			min = v
		}
	}
	avg = sum / uint64(r.count)
	return last, avg, max, min, true
}

type LatencyProber struct {
	targets     []string
	targetsFile string
	interval    time.Duration
	mu          sync.RWMutex
	results     map[string]*ringBuffer
}

func NewLatencyProber(targets []string, targetsFile string, intervalSec int) *LatencyProber {
	if intervalSec < 1 {
		intervalSec = 5
	}
	results := make(map[string]*ringBuffer)
	for _, t := range targets {
		results[t] = newRingBuffer(60)
	}
	return &LatencyProber{
		targets:     targets,
		targetsFile: targetsFile,
		interval:    time.Duration(intervalSec) * time.Second,
		results:     results,
	}
}

// reloadTargets re-reads the targets file (if configured) and reconciles the probe
// set: new IPs get a ring buffer, removed IPs are dropped. A missing file is a
// no-op (targets just stay as they are). Safe to call concurrently with probing.
func (p *LatencyProber) reloadTargets() {
	if p.targetsFile == "" {
		return
	}
	data, err := os.ReadFile(p.targetsFile)
	if err != nil {
		// Missing/unreadable file: leave existing targets untouched.
		return
	}

	want := make(map[string]struct{})
	for _, raw := range strings.FieldsFunc(string(data), func(r rune) bool { return r == ',' || r == '\n' || r == '\r' }) {
		ip := strings.TrimSpace(raw)
		if ip != "" {
			want[ip] = struct{}{}
		}
	}
	// Static --latency-targets are always kept.
	for _, t := range p.targets {
		want[t] = struct{}{}
	}

	p.mu.Lock()
	defer p.mu.Unlock()
	for ip := range want {
		if _, ok := p.results[ip]; !ok {
			p.results[ip] = newRingBuffer(60)
			log.Printf("latency: added target %s", ip)
		}
	}
	for ip := range p.results {
		if _, ok := want[ip]; !ok {
			delete(p.results, ip)
			log.Printf("latency: removed target %s", ip)
		}
	}
}

func (p *LatencyProber) Run(ctx context.Context) {
	if !p.Enabled() {
		return
	}

	log.Printf("latency prober started: targets=%v targets-file=%q interval=%v", p.targets, p.targetsFile, p.interval)

	p.reloadTargets()

	ticker := time.NewTicker(p.interval)
	defer ticker.Stop()

	p.probeAll()

	for {
		select {
		case <-ctx.Done():
			log.Printf("latency prober stopped")
			return
		case <-ticker.C:
			p.reloadTargets()
			p.probeAll()
		}
	}
}

func (p *LatencyProber) probeAll() {
	p.mu.RLock()
	targets := make([]string, 0, len(p.results))
	for t := range p.results {
		targets = append(targets, t)
	}
	p.mu.RUnlock()

	var wg sync.WaitGroup
	for _, target := range targets {
		wg.Add(1)
		go func(t string) {
			defer wg.Done()
			rtt, err := pingOnce(t, 2*time.Second)
			if err != nil {
				log.Printf("latency: ping %s failed: %v", t, err)
				return
			}
			p.mu.Lock()
			if rb, ok := p.results[t]; ok {
				rb.push(rtt)
			}
			p.mu.Unlock()
		}(target)
	}
	wg.Wait()
}

var rttRegex = regexp.MustCompile(`time=([\d.]+)\s*(ms|usec|s)`)

func pingOnce(target string, timeout time.Duration) (uint64, error) {
	cmd := exec.CommandContext(context.Background(), "ping",
		"-c", "1",
		"-W", fmt.Sprintf("%d", int(timeout.Seconds())),
		target,
	)

	var out bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &out

	if err := cmd.Run(); err != nil {
		return 0, fmt.Errorf("ping command failed: %w: %s", err, out.String())
	}

	matches := rttRegex.FindStringSubmatch(out.String())
	if len(matches) != 3 {
		return 0, fmt.Errorf("could not parse RTT from output: %s", out.String())
	}

	val, err := strconv.ParseFloat(matches[1], 64)
	if err != nil {
		return 0, fmt.Errorf("could not parse RTT value %q: %w", matches[1], err)
	}

	var rttNS uint64
	switch matches[2] {
	case "ms":
		rttNS = uint64(val * 1_000_000)
	case "usec":
		rttNS = uint64(val * 1_000)
	case "s":
		rttNS = uint64(val * 1_000_000_000)
	default:
		rttNS = uint64(val * 1_000_000)
	}

	return rttNS, nil
}

func (p *LatencyProber) GetStats(ip string) (LatencyStats, bool) {
	p.mu.RLock()
	defer p.mu.RUnlock()

	rb, ok := p.results[ip]
	if !ok {
		return LatencyStats{}, false
	}

	last, avg, max, min, ok := rb.stats()
	if !ok {
		return LatencyStats{}, false
	}

	return LatencyStats{
		RTTNS: last,
		AvgNS: avg,
		MaxNS: max,
		MinNS: min,
	}, true
}

func (p *LatencyProber) AllStats() map[string]LatencyStats {
	p.mu.RLock()
	defer p.mu.RUnlock()

	result := make(map[string]LatencyStats, len(p.results))
	for ip := range p.results {
		rb := p.results[ip]
		last, avg, max, min, ok := rb.stats()
		if ok {
			result[ip] = LatencyStats{
				RTTNS: last,
				AvgNS: avg,
				MaxNS: max,
				MinNS: min,
			}
		}
	}
	return result
}

func (p *LatencyProber) Targets() []string {
	return p.targets
}

func (p *LatencyProber) Enabled() bool {
	return len(p.targets) > 0 || p.targetsFile != ""
}

func (p *LatencyProber) String() string {
	return fmt.Sprintf("LatencyProber{targets: [%s], interval: %v}",
		strings.Join(p.targets, ", "), p.interval)
}
