FROM golang:1.23 AS builder
WORKDIR /src
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/neubot/dash.git .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -trimpath -ldflags="-s -w" \
    -o /dash-client ./cmd/dash-client

FROM debian:bookworm-slim
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        iproute2 \
        iputils-ping && \
    rm -rf /var/lib/apt/lists/*
COPY --from=builder /dash-client /usr/local/bin/dash-client
RUN chmod 0755 /usr/local/bin/dash-client
ENTRYPOINT ["sleep"]
CMD ["infinity"]
