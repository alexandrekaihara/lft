FROM golang:1.23 as build
WORKDIR /go/src/github.com/neubot/dash
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/neubot/dash.git .
RUN CGO_ENABLED=0 go build -v -tags netgo \
    -ldflags "-s -w -extldflags \"-static\"" ./cmd/dash-server

FROM gcr.io/distroless/static@sha256:2ad95019a0cbf07e0f917134f97dd859aaccc09258eb94edcb91674b3c1f448f
COPY --from=build /go/src/github.com/neubot/dash/dash-server /dash-server
EXPOSE 80/tcp 443/tcp
WORKDIR /
ENTRYPOINT ["/dash-server"]
