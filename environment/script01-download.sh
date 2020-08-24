#!/bin/bash

set -e
mkdir -p packages/nsc-python{27,36}
chmod a+rwx packages/nsc-python*

docker run -v $PWD:/mnt --rm centos/python-27-centos7 \
        bash -c "pip install --upgrade pip && \
        pip download \
        -d /mnt/packages/nsc-python27 \
        -r /mnt/requirements-py27-origin.txt"

docker run -v $PWD:/mnt --rm centos/python-36-centos7 \
        bash -c "pip install --upgrade pip &&
        pip download \
        -d /mnt/packages/nsc-python36 \
        -r /mnt/requirements-py36-origin.txt"

tar cfz packages.tar.gz packages/
