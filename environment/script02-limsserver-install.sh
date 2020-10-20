#!/bin/bash

# Run on the LIMS server. 

set -e
yum install python2 python3
rm -fr packages/*
tar xfz packages.tar.gz
pip3 install --no-index --find-links packages/nsc-python36 virtualenv

/usr/local/bin/virtualenv -p python2 /opt/nsc/envs/nsc-python27
source /opt/nsc/envs/nsc-python27/bin/activate
pip install --upgrade --no-index --find-links packages/nsc-python27/ -r requirements-py27-origin.txt
deactivate

python3 -m venv /opt/nsc/envs/nsc-python36
source /opt/nsc/envs/nsc-python36/bin/activate
pip install --upgrade packages/nsc-python36/pip-*-py2.py3-none-any.whl
#pip install --no-index --find-links --upgrade pip
pip install --upgrade --no-index --find-links packages/nsc-python36/ -r requirements-py36-origin.txt
deactivate

ln -sf /opt/nsc/envs/nsc-python27/bin/python /usr/bin/nsc-python27
printf '#!/bin/bash\nsource /opt/nsc/envs/nsc-python36/bin/activate\npython "$@"\n' > /usr/bin/nsc-python36
chmod a+rx /usr/bin/nsc-python36
ln -sf nsc-python36 /usr/bin/nsc-python3
ln -sf nsc-python36 /usr/bin/nsc-python35
