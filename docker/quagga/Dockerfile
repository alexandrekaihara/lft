FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    iproute2 net-tools iputils-ping tcpdump quagga psmisc \
    && rm -rf /var/lib/apt/lists/*
RUN chown -R quagga:quagga /etc/quagga
RUN touch /etc/quagga/zebra.conf /etc/quagga/ospfd.conf
RUN chown quagga:quagga /etc/quagga/*
RUN mkdir -p /var/run/quagga && chown quagga:quagga /var/run/quagga

CMD ["tail", "-f", "/dev/null"]
