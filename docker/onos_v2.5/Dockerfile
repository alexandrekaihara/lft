FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV JAVA_TOOL_OPTIONS="-Djdk.util.zip.disableZip64ExtraFieldValidation=true"
RUN apt-get update && apt-get install -y \
    openjdk-11-jre-headless \
    curl \
    procps \
    tar \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m onos
WORKDIR /home/onos
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ARG ONOS_VERSION=2.5.0
RUN curl -L https://repo1.maven.org/maven2/org/onosproject/onos-releases/${ONOS_VERSION}/onos-${ONOS_VERSION}.tar.gz -o onos.tar.gz && \
    tar -xzf onos.tar.gz --strip-components=1 && \
    rm onos.tar.gz
COPY .onos-apps-ONOS_Link_Quality_Measurement-oar.oar ./apps/link-quality.oar
RUN chown -R onos:onos /home/onos
USER onos
EXPOSE 6653 8181 8101

ENTRYPOINT ["./bin/onos-service", "server"]
