# LIMS scripts python dependency management

Python packages are stored in two virtual environments. The environments can be installed on the LIMS server.

* nsc-python27: Packages for scripts using python 2.7.
* nsc-python36: Packages for scripts using python 3.6.

The scripts here use a Docker container to download the required Python packages. It is driven by the requirements*.txt files, that contain a list of required packages.


## LIMS server python environments installation procedure

1. Download and dependency resolution: Use any host connected to the internet with docker.

`script01-download.sh`: Downloads the pip packages into the `packages/` directory and packs them into a tar file.

2. Transfer the tar file to a LIMS server.
3. Commit any changes to the requirements files, and push! (only required if making changes to the list of packages)
4. Pull the lims repo on the LIMS server, to get the updated requirements files. If updating a production server, do this:
  - Pull the repo on the corresponding dev server (e.g. ous-lims -> pull on dev-lims)
  - Deploy the HEAD revision using the scripts in ../deploy/.
  - Alternatively, make the changes to the requirements manually directly on the prod server.
5. Place the tar file in the directory containing this file on the LIMS server (e.g. /opt/gls/clarity/customextensions/lims/environment). If updating a prod server, place it on the prod server itself. Do it after step 4, or the files may be wiped out again when deploying.
6. Run `script02-limsserver-install.sh` on the LIMS server as the root user to install the environments under `/opt/nsc/envs`, and create symlinks to the python interpreters.
7. Test by running:
```
$ nsc-python27
>>> import matplotlib
>>>
```
(And test similarly for python 3.6.)
8. Delete packages and tar files (`rm -r packages*`) on the local computer and on the LIMS server, to clean up. (Note that on a prod server it's especially important to clean up, as otherwise, the deployment script may have trouble deleting the leftover files in a future deployment.).

