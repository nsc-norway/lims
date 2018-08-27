#!/bin/bash
set -e
TAG=`date "+lims_%Y%m%d"$1`
./tag.sh $TAG
./deploy-ous.sh $TAG
