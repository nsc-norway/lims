#!/bin/bash

set -e
yum install python2 python3
tar xf packages.tar
pip3 install --no-index --find-links packages/nsc-python36 virtualenv

virtualenv -p python2 /opt/nsc/envs/nsc-python27
source /opt/nsc/envs/nsc-python27/bin/activate
pip install --no-index --find-links packages/nsc-python27/ -r requirements-py27-origin.txt
deactivate

virtualenv -p python3 /opt/nsc/envs/nsc-python36
source /opt/nsc/envs/nsc-python36/bin/activate
pip install --no-index --find-links packages/nsc-python36/ -r requirements-py36-origin.txt
deactivate

ln -sf /opt/nsc/envs/nsc-python27/bin/python /usr/bin/nsc-python27
ln -sf /opt/nsc/envs/nsc-python36/bin/python /usr/bin/nsc-python36
