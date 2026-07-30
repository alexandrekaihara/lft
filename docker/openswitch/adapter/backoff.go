package main

import "time"

type backoffConfig struct {
	min    time.Duration
	max    time.Duration
	factor float64
	attempt int
}

func (b *backoffConfig) next() time.Duration {
	d := b.min
	for i := 0; i < b.attempt; i++ {
		d = time.Duration(float64(d) * b.factor)
		if d > b.max {
			d = b.max
			break
		}
	}
	b.attempt++
	return d
}

func (b *backoffConfig) reset() {
	b.attempt = 0
}
