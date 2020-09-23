#!/bin/bash

# Run on the LIMS server. 

set -e
yum install python2 python3
tar xfz packages.tar.gz
pip3 install --no-index --find-links packages/nsc-python36 virtualenv

/usr/local/bin/virtualenv -p python2 /opt/nsc/envs/nsc-python27
source /opt/nsc/envs/nsc-python27/bin/activate
pip install --no-index --find-links packages/nsc-python27/ -r requirements-py27-origin.txt
deactivate

python3 -m venv /opt/nsc/envs/nsc-python36
source /opt/nsc/envs/nsc-python36/bin/activate
pip install --upgrade pip
pip install --no-index --find-links packages/nsc-python36/ -r requirements-py36-origin.txt
deactivate

ln -sf /opt/nsc/envs/nsc-python27/bin/python /usr/bin/nsc-python27
ln -sf /opt/nsc/envs/nsc-python36/bin/python /usr/bin/nsc-python36
ln -sf nsc-python36 /usr/bin/nsc-python3
