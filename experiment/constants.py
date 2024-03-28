# Experiments
INTERVAL = "PT2M"
MAX_RUNS = 10
RESULTS_PATH = "results/data/"
REPEAT_INTERVAL = "PT3M"
THROUGHPUT_JSON_FORMAT = "throughput_%n.json"
THROUGHPUT_JSON_FORMAT_WILDCARD = "throughput_*.json"
RTT_JSON_FORMAT = "rtt_%n.json"
RTT_JSON_FORMAT_WILDCARD = "rtt_*.json"
LATENCY_JSON_FORMAT = "latency_%n.json"
LATENCY_JSON_FORMAT_WILDCARD = "latency_*.json"
PERFSONAR_JSON_OUTPUT_FORMAT = "json"
THROUGHPUT_EXPERIMENT_NAME = "Throughput"
RTT_EXPERIMENT_NAME = "Round Trip Time (RTT)"
LATENCY_EXPERIMENT_NAME = "Latency"


# Wired
EMU_EMU_WIRED_PREFIX = "wired_emu_emu_"
EMU_PHY_WIRED_PREFIX = "wired_emu_phy_"
PHY_PHY_WIRED_PREFIX = "wired_phy_phy_"

## Emu Emu
PERFSONAR_TESTPOINT_UBUNTU = "alexandremitsurukaihara/lft:perfsonar-testpoint-ubuntu"
USR_SBIN_INIT_COMMAND = "/usr/sbin/init"
EMU_EMU_WIRED_H1_IP = "10.0.0.1"
EMU_EMU_WIRED_H2_IP = "10.0.0.2"

EMU_EMU_WIRED_HOST_IP = "192.0.0.1" 


## Emu Phy
EMU_PHY_WIRED_H1_IP = "10.0.0.2"
EMU_PHY_WIRED_H2_IP = "38.68.234.32"


## Phy Phy
PHY_PHY_WIRED_H1_IP = "38.68.234.32"
PHY_PHY_WIRED_H2_IP = "38.68.234.31"


# Wireless
EMU_EMU_WIRELESS_PREFIX = "wireless_emu_emu_"
EMU_PHY_WIRELESS_PREFIX = "wireless_emu_phy_"
PHY_PHY_WIRELESS_PREFIX = "wireless_phy_phy_"


# Emu Emu Wireless
SRSRAN_PERFSONAR_UHD_IMAGE = "alexandremitsurukaihara/lft:srsran-perfsonar-uhd4"


# Emu Emu Wireless
EMU_EMU_WIRELESS_EPC_IP_ADDR = "172.16.0.1"
EMU_EMU_WIRELESS_UE_IP_ADDR = "172.16.0.2"

EMU_PHY_WIRELESS_EPC_IP_ADDR = "172.16.0.1"
EMU_PHY_WIRELESS_UE_IP_ADDR = "172.16.0.2"

PHY_PHY_WIRELESS_EPC_IP_ADDR = "172.16.0.1"
PHY_PHY_WIRELESS_UE_IP_ADDR = "172.16.0.2"

THROUGHPUT = "Throughput"
RTT = "RTT"
LATENCY = "Latency"
JITTER = "Jitter"