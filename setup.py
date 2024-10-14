# Copyright (C) 2024 Alexandre Mitsuru Kaihara
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

# This file is for defining a package in Python
from setuptools import setup, find_packages
from setuptools.command.install import install
import subprocess

class CustomInstall(install):
    def run(self):
        subprocess.run(f"chmod +X dependencies.sh", shell=True)
        subprocess.run(f"sudo ./dependencies.sh", shell=True)
        install.run(self)
    
setup(
    name='profissa_lft',
    version='1.0.9',
    packages=find_packages(),
    install_requires=['pandas'],
    author='Alexandre Mitsuru Kaihara',
    author_email='alexandreamk1@gmail.com',
    description='LFT is a framework designed to facilitate the creation of lightweight network topologies with ease. Using Docker containers, it is possible to add any container to the network to provide network services or even emulate network devices, such as switches, controllers (in Software Defined Networking). This project has integration with OpenvSwitch to emulate the network forwarding devices and srsRAN 4G to emulate wireless links for Fog and Edge application scenarios.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/alexandrekaihara/lft    ',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.9',
    cmdclass= {
        'install': CustomInstall
    },
    include_package_data=True
)

