#!/bin/bash

set -e

docker run -v $PWD:/opt/nsc --rm centos/python-27-centos7 \
        bash -c "source /opt/nsc/envs/nsc-python27/bin/activate && \
        pip install --upgrade pip && \
        pip install -r /opt/nsc/requirements-py27-origin.txt"

docker run -v $PWD:/opt/nsc --rm centos/python-36-centos7 \
        bash -c "source /opt/nsc/envs/nsc-python36/bin/activate && \
        pip install -r /opt/nsc/requirements-py36-origin.txt"

tar cfz envs.tar.gz envs/
