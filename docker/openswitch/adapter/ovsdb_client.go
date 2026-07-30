package main

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/ovn-org/libovsdb/cache"
	"github.com/ovn-org/libovsdb/client"
	"github.com/ovn-org/libovsdb/model"
)

type OVSDBChangeEvent struct {
	Table string
	Op    string
	Old   model.Model
	New   model.Model
}

type OVSDBClient struct {
	client   client.Client
	cfg      *Config
	mu       sync.RWMutex
	subs     []chan OVSDBChangeEvent
	stopCh   chan struct{}
	readyCh  chan struct{}
}

func NewOVSDBClient(cfg *Config) *OVSDBClient {
	return &OVSDBClient{
		cfg:     cfg,
		subs:    make([]chan OVSDBChangeEvent, 0),
		stopCh:  make(chan struct{}),
		readyCh: make(chan struct{}),
	}
}

func (o *OVSDBClient) Subscribe() chan OVSDBChangeEvent {
	o.mu.Lock()
	defer o.mu.Unlock()
	ch := make(chan OVSDBChangeEvent, 256)
	o.subs = append(o.subs, ch)
	return ch
}

func (o *OVSDBClient) Unsubscribe(ch chan OVSDBChangeEvent) {
	o.mu.Lock()
	defer o.mu.Unlock()
	for i, sub := range o.subs {
		if sub == ch {
			o.subs = append(o.subs[:i], o.subs[i+1:]...)
			close(ch)
			return
		}
	}
}

func (o *OVSDBClient) emit(evt OVSDBChangeEvent) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	for _, ch := range o.subs {
		select {
		case ch <- evt:
		default:
			log.Printf("ovsdb: subscriber channel full, dropping event for table=%s", evt.Table)
		}
	}
}

func (o *OVSDBClient) Ready() <-chan struct{} {
	return o.readyCh
}

func (o *OVSDBClient) Run(ctx context.Context) error {
	dbModel, err := model.NewClientDBModel("Open_vSwitch", map[string]model.Model{
		"Open_vSwitch": &OVSDBRoot{},
		"Bridge":       &OVSDBBridge{},
		"Port":         &OVSDBPort{},
		"Interface":    &OVSDBInterface{},
	})
	if err != nil {
		return err
	}

	endpoint := "unix:" + o.cfg.OVSDBSocket

	backoff := &backoffConfig{
		min:    1 * time.Second,
		max:    30 * time.Second,
		factor: 2,
	}

	for {
		attemptStart := time.Now()

		ovsClient, err := client.NewOVSDBClient(dbModel, client.WithEndpoint(endpoint))
		if err != nil {
			log.Printf("ovsdb: client creation error: %v", err)
			if o.sleepWithBackoff(ctx, backoff) {
				return ctx.Err()
			}
			continue
		}

		err = ovsClient.Connect(ctx)
		if err != nil {
			log.Printf("ovsdb: connect error: %v", err)
			ovsClient.Disconnect()
			if o.sleepWithBackoff(ctx, backoff) {
				return ctx.Err()
			}
			continue
		}

		log.Printf("ovsdb: connected to %s", endpoint)
		backoff.reset()

		ovsClient.Cache().AddEventHandler(&cache.EventHandlerFuncs{
			AddFunc: func(table string, m model.Model) {
				o.emit(OVSDBChangeEvent{Table: table, Op: "add", New: m})
			},
			UpdateFunc: func(table string, old, new model.Model) {
				o.emit(OVSDBChangeEvent{Table: table, Op: "update", Old: old, New: new})
			},
			DeleteFunc: func(table string, m model.Model) {
				o.emit(OVSDBChangeEvent{Table: table, Op: "delete", Old: m})
			},
		})

		_, err = ovsClient.Monitor(ctx,
			ovsClient.NewMonitor(
				client.WithTable(&OVSDBRoot{}),
				client.WithTable(&OVSDBBridge{}),
				client.WithTable(&OVSDBPort{}),
				client.WithTable(&OVSDBInterface{}),
			),
		)
		if err != nil {
			log.Printf("ovsdb: monitor error: %v", err)
			ovsClient.Disconnect()
			if o.sleepWithBackoff(ctx, backoff) {
				return ctx.Err()
			}
			continue
		}

		o.mu.Lock()
		o.client = ovsClient
		o.mu.Unlock()

		select {
		case o.readyCh <- struct{}{}:
		default:
		}

		select {
		case <-ctx.Done():
			ovsClient.Disconnect()
			return ctx.Err()
		case <-ovsClient.DisconnectNotify():
			log.Printf("ovsdb: disconnected, will reconnect")
			o.mu.Lock()
			o.client = nil
			o.mu.Unlock()
			if time.Since(attemptStart) < 5*time.Second {
				time.Sleep(5*time.Second - time.Since(attemptStart))
			}
		}
	}
}

func (o *OVSDBClient) sleepWithBackoff(ctx context.Context, b *backoffConfig) bool {
	d := b.next()
	log.Printf("ovsdb: reconnecting in %v", d)
	select {
	case <-time.After(d):
		return false
	case <-ctx.Done():
		return true
	}
}

func (o *OVSDBClient) ListInterfaces() ([]OVSDBInterface, error) {
	o.mu.RLock()
	c := o.client
	o.mu.RUnlock()
	if c == nil {
		return nil, ErrNotConnected
	}
	var result []OVSDBInterface
	err := c.List(context.Background(), &result)
	return result, err
}

func (o *OVSDBClient) ListPorts() ([]OVSDBPort, error) {
	o.mu.RLock()
	c := o.client
	o.mu.RUnlock()
	if c == nil {
		return nil, ErrNotConnected
	}
	var result []OVSDBPort
	err := c.List(context.Background(), &result)
	return result, err
}

func (o *OVSDBClient) ListBridges() ([]OVSDBBridge, error) {
	o.mu.RLock()
	c := o.client
	o.mu.RUnlock()
	if c == nil {
		return nil, ErrNotConnected
	}
	var result []OVSDBBridge
	err := c.List(context.Background(), &result)
	return result, err
}

func (o *OVSDBClient) Close() {
	o.mu.Lock()
	defer o.mu.Unlock()
	if o.client != nil {
		o.client.Disconnect()
		o.client = nil
	}
	for _, ch := range o.subs {
		close(ch)
	}
	o.subs = nil
}

var ErrNotConnected = fmt.Errorf("ovsdb client not connected")
