package main

import (
	"os"
	"path/filepath"
	"sort"
	"testing"
)

func sortedTargets(p *LatencyProber) []string {
	p.mu.RLock()
	defer p.mu.RUnlock()
	out := make([]string, 0, len(p.results))
	for t := range p.results {
		out = append(out, t)
	}
	sort.Strings(out)
	return out
}

func TestReloadTargets_AddsAndRemoves(t *testing.T) {
	dir := t.TempDir()
	file := filepath.Join(dir, "targets.conf")

	p := NewLatencyProber(nil, file, 5)

	// Initial: empty file -> no targets.
	if got := sortedTargets(p); len(got) != 0 {
		t.Fatalf("expected no targets, got %v", got)
	}

	// Write two targets.
	if err := os.WriteFile(file, []byte("10.0.0.1,10.0.0.2\n"), 0644); err != nil {
		t.Fatal(err)
	}
	p.reloadTargets()
	if got := sortedTargets(p); len(got) != 2 || got[0] != "10.0.0.1" || got[1] != "10.0.0.2" {
		t.Fatalf("expected [10.0.0.1 10.0.0.2], got %v", got)
	}

	// Replace with one different target.
	if err := os.WriteFile(file, []byte("10.0.0.3\n"), 0644); err != nil {
		t.Fatal(err)
	}
	p.reloadTargets()
	if got := sortedTargets(p); len(got) != 1 || got[0] != "10.0.0.3" {
		t.Fatalf("expected [10.0.0.3], got %v", got)
	}

	// Delete the file -> existing targets untouched (no-op).
	if err := os.Remove(file); err != nil {
		t.Fatal(err)
	}
	p.reloadTargets()
	if got := sortedTargets(p); len(got) != 1 || got[0] != "10.0.0.3" {
		t.Fatalf("expected targets unchanged after file removal, got %v", got)
	}
}

func TestReloadTargets_KeepsStaticTargets(t *testing.T) {
	dir := t.TempDir()
	file := filepath.Join(dir, "targets.conf")

	p := NewLatencyProber([]string{"10.0.0.99"}, file, 5)
	if got := sortedTargets(p); len(got) != 1 || got[0] != "10.0.0.99" {
		t.Fatalf("expected static target, got %v", got)
	}

	// File lists a different IP; static target must be retained.
	if err := os.WriteFile(file, []byte("10.0.0.1\n"), 0644); err != nil {
		t.Fatal(err)
	}
	p.reloadTargets()
	if got := sortedTargets(p); len(got) != 2 {
		t.Fatalf("expected static + file target, got %v", got)
	}

	// Empty file -> static target still retained.
	if err := os.WriteFile(file, []byte(""), 0644); err != nil {
		t.Fatal(err)
	}
	p.reloadTargets()
	if got := sortedTargets(p); len(got) != 1 || got[0] != "10.0.0.99" {
		t.Fatalf("expected static target retained, got %v", got)
	}
}

func TestReloadTargets_NoFileConfigured(t *testing.T) {
	p := NewLatencyProber([]string{"10.0.0.1"}, "", 5)
	p.reloadTargets() // must not panic / must be no-op
	if got := sortedTargets(p); len(got) != 1 || got[0] != "10.0.0.1" {
		t.Fatalf("expected static target unchanged, got %v", got)
	}
}
