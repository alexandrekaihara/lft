# iperf3 endpoint used by the LFT topologies (cl*/ds* containers).
# Reconstructed with `docker history` from the image running in production
# on lft-vm: ubuntu:22.04 base + the four tools, bash-login entrypoint.
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    iperf3 \
    iproute2 \
    iputils-ping \
    tcpdump \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["bash", "-lc"]
