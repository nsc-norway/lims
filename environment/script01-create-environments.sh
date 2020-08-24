#!/bin/bash

set -e
mkdir -p envs
mkdir envs/nsc-python{27,36}
docker run -v $PWD:/opt/nsc --rm centos/python-27-centos7 bash -c "virtualenv /opt/nsc/envs/nsc-python27"
docker run -v $PWD:/opt/nsc --rm centos/python-36-centos7 bash -c "virtualenv /opt/nsc/envs/nsc-python36"

