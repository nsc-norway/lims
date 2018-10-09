#!/bin/bash
set -e
if [ `hostname` == "sandbox-lims.sequencing.uio.no" ]
then
	SCRIPT=./deploy-cees.sh
elif [ `hostname` == "dev-lims.sequencing.uio.no" ]
then
	SCRIPT=./deploy-ous.sh
fi
TAG=`date "+lims_%Y%m%d"$1`
./tag.sh $TAG
$SCRIPT $TAG
