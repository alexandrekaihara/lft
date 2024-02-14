# Experiments
INTERVAL = "PT2M"
MAX_RUNS = 10
RESULTS_PATH = "results/data/"
REPEAT_INTERVAL = "PT3M"
THROUGHPUT_JSON_FORMAT = "throughput_%n.json"
PERFSONAR_JSON_OUTPUT_FORMAT = "json"


# Wired
EMU_EMU_WIRED_PREFIX = "wired_emu_emu_"
EMU_PHY_WIRED_PREFIX = "wired_emu_phy_"
PHY_PHY_WIRED_PREFIX = "wired_phy_phy_"


# Emu Emu Wired
PERFSONAR_TESTPOINT_UBUNTU = "alexandremitsurukaihara/lft:perfsonar-testpoint-ubuntu"
USR_SBIN_INIT_COMMAND = "/usr/sbin/init"
EMU_EMU_WIRED_H1_IP = "10.0.0.1"
EMU_EMU_WIRED_H2_IP = "10.0.0.2"

EMU_EMU_WIRED_HOST_IP = "192.0.0.1" 


# Emu Phy Wired
EMU_PHY_WIRED_H1_IP = "10.0.0.2"
EMU_PHY_WIRED_H2_IP = "38.68.234.32"


# Phy Phy Wired
PHY_PHY_WIRED_H1_IP = "38.68.234.35"
PHY_PHY_WIRED_H2_IP = "38.68.234.32"


# Emu Emu Wireless
SRSRAN_PERFSONAR_UHD_IMAGE = "alexandremitsurukaihara/lft:srsran-perfsonar-uhd4"


# Emu Emu Wireless
EMU_EMU_WIRELESS_EPC_IP_ADDR = "172.16.0.1"
EMU_EMU_WIRELESS_UE_IP_ADDR = "172.16.0.2"