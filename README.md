# Lightweight Fog Testbed (LFT)
LFT is a framework designed to facilitate the creation of lightweight network topologies with ease. Using Docker containers, it is possible to add any container to the network to provide network services or even emulate network devices, such as switches, controllers (in Software Defined Networking). This project has integration with OpenvSwitch to emulate the network forwarding devices and srsRAN 4G to emulate wireless links for Fog and Edge application scenarios.

## 1. Requirement
This framework was developed and tested on Ubuntu Desktop 24.04 LTS. We recommend this Linux version.

## 2. Installation
To install the project you need to run:

```
pip3 install profissa_lft
```

In case of any missing dependency you can manually clone the repository and run the dependencies script:

```
git clone https://github.com/alexandrekaihara/lft
cd lft
chmod +X dependencies.sh
./dependencies.sh
```

## 3. First run
On the source root of the project run:

```
cd examples
python3 simpleSDNTopology.py
```

## 4. Troubleshooting
If you face any issue while running any LFT scrips:
1. Check if all dependencies are installed
2. Check if you are using the correct version of Ubuntu Desktop
3. Check if the containers are already instantiated on docker ```docker ps -a```. If so, then remove them by using ```docker system prune``` or forcefully stop them ```docker rm -f containerName```
4. Verify if the docker image that you are trying to instantiate with LFT exists on your local machine ```docker images``` or exists on [Docker Hub|https://hub.docker.com/].
5. Check if the image was built correctly. See docker folder for more information.