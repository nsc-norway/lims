#!/bin/bash

DIR=`dirname $0`

python $DIR/timeexomes.py
python $DIR/timebases.py

