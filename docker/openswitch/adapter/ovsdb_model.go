package main

type OVSDBBridge struct {
	UUID         string            `ovsdb:"_uuid"`
	Name         string            `ovsdb:"name"`
	DatapathType string            `ovsdb:"datapath_type"`
	Ports        []string          `ovsdb:"ports"`
	ExternalIDs  map[string]string `ovsdb:"external_ids"`
}

type OVSDBPort struct {
	UUID        string            `ovsdb:"_uuid"`
	Name        string            `ovsdb:"name"`
	Interfaces  []string          `ovsdb:"interfaces"`
	ExternalIDs map[string]string `ovsdb:"external_ids"`
	VLANMode    *string           `ovsdb:"vlan_mode"`
	Tag         *int              `ovsdb:"tag"`
	Trunks      []int             `ovsdb:"trunks"`
}

type OVSDBInterface struct {
	UUID        string            `ovsdb:"_uuid"`
	Name        string            `ovsdb:"name"`
	Type        string            `ovsdb:"type"`
	LinkState   *string           `ovsdb:"link_state"`
	AdminState  *string           `ovsdb:"admin_state"`
	MAC         *string           `ovsdb:"mac_in_use"`
	MTU         *int              `ovsdb:"mtu"`
	Statistics  map[string]int    `ovsdb:"statistics"`
	ExternalIDs map[string]string `ovsdb:"external_ids"`
	Options     map[string]string `ovsdb:"options"`
	Ofport      *int              `ovsdb:"ofport"`
}

type OVSDBRoot struct {
	UUID    string   `ovsdb:"_uuid"`
	Bridges []string `ovsdb:"bridges"`
}
