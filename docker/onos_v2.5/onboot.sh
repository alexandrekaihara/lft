./bin/onos-service server &

while ! nc -z localhost 8101; do   
  sleep 3
done

./bin/onos localhost app activate org.onosproject.proxyarp
./bin/onos localhost app install! ./apps/link-quality.oar
tail -f ./apache-karaf-*/data/log/karaf.log
