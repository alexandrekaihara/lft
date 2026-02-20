FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    iperf3 \
    iproute2 \
    iputils-ping \
    tcpdump \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["bash", "-lc"]
