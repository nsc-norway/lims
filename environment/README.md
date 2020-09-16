# LIMS scripts python dependency management

Python packages are stored in two virtual environments. The environments can be installed on the LIMS server.

* nsc-python27: Packages for scripts using python 2.7.
* nsc-python36: Packages for scripts using python 3.6.

The scripts here use a Docker container to download the required Python packages. It is driven by the requirements*.txt files, that contain a list of required packages.


## LIMS server python environments installation procedure

1. Download and dependency resolution: Use any host connected to the internet with docker.

`script01-download.sh`: Downloads the pip packages into the `packages/` directory and packs them into a tar file.

2. Transfer the tar file to a LIMS server.
3. Place the tar file in the directory containing this file on the LIMS server (e.g. /opt/gls/clarity/customextensions/lims/environment).
4. Run `script02-limsserver-install.sh` as the root user to install the environments under `/opt/nsc/envs`, and create symlinks to the python interpreters.
5. Test by running:
```
$ nsc-python27
>>> import matplotlib
>>>
```
And similarly for python 3.6.
6. Delete packages and tar files (`rm -r packages*`).
