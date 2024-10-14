# Lightweight Fog Testbed (LFT)
LFT is a framework designed to facilitate the creation of lightweight network topologies with ease. Using Docker containers, it is possible to add any container to the network to provide network services or even emulate network devices, such as switches, controllers (in Software Defined Networking). This project has integration with OpenvSwitch to emulate the network forwarding devices and srsRAN 4G to emulate wireless links for Fog and Edge application scenarios.

## Requirement
This framework was developed and tested on Ubuntu Desktop 24.04 LTS. We recommend this Linux version.

## Installation
To install the project you need to run:

```
git clone https://github.com/alexandrekaihara/lft
cd lft
chmod +X dependencies.sh
./dependencies.sh
```

## First run
On the source root of the project run:

'''
python3 
'''