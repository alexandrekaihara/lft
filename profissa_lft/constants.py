# Docker commands 
DOCKER_COMMAND = "docker"
DOCKER_RUN = DOCKER_COMMAND + " run"

# Docker run options
NETWORK = "--network"
NAME = "--name"
PRIVILEGED = "--privileged"
DNS = "--dns"
MEMORY = "--memory"
CPUS = "--cpus"

# UE config file
RF_SECTION = "rf"
DEVICE_ARGS_ATTR = "device_args"
DEVICE_NAME_ATTR = "device_name" 
TX_GAIN_ATTR = "tx_gain"
RX_GAIN_ATTR = "rx_gain"
USIM_SECTION = "usim" 
ALGORITHM_ATTR = "algo"
IMSI_ATTR = "imsi"

## PHY section
PHY_SECTION = "phy"
CORRECT_SYNC_ERROR = "correct_sync_error"

# EPC config file
MME_SECTION = "mme"
MME_BIND_ADDR = "mme_bind_addr"

SPGW_SECTION = "spgw"
GTPU_BIND_ADDR = "gtpu_bind_addr"
SGI_IF_ADDR = "sgi_if_addr"

# eNB config file
ENB_SECTION = "enb"
MME_ADDR = "mme_addr"
GTP_BIND_ADDR = "gtp_bind_addr"
S1C_BIND_ADDR = "s1c_bind_addr"