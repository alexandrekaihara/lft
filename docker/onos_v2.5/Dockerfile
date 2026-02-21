FROM onosproject/onos:2.5.0

USER root

RUN mkdir -p /home/onos && \
    chown -R onos:onos /home/onos

RUN ln -s /root/onos/apache-karaf-* /home/onos/apache-karaf-4.2.14

USER root
