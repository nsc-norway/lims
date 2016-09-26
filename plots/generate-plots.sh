#!/bin/bash

RELATIVE_DIR=`dirname $0`
DIR=`readlink -f $RELATIVE_DIR`

pushd /var/www/html/plots
python $DIR/timeexomes.py
python $DIR/timebases.py
popd

