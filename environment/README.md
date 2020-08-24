# LIMS scripts python dependency management

Python packages are stored in two virtual environments. The environments can be installed on the LIMS server.

* nsc-python27: Packages for scripts using python 2.7.
* nsc-python36: Packages for scripts using python 3.6.

The scripts here use a Docker container to download the required Python packages. It is driven by the requirements*.txt files, that contain a list of required packages.


## LIMS server python environments installation procedure

1. Download and dependency resolution: Use any host connected to the internet with docker.

`script01-create-environments.sh`: Creates virtual environments for each of the python versions under the `envs/` directory.

`script02-download.sh`: Downloads the pip packages into the virtual environments and then creates a tar file `envs.tar` containing the environments with packages.

2. Transfer the tar file to a LIMS server.
3. Unpack the tar file in `/opt/nsc` [exactly this location must be used, based on the previous commands]:

```
sudo mkdir -p /opt/nsc
cd /opt/nsc
sudo tar xfz envs.tar.gz
```

4. Create links to the python binaries:
```
for nscpython in nsc-python27 nsc-python36
do
    sudo ln -s /opt/nsc/envs/$nscpython/bin/python /usr/bin/$nscpython
done
```
