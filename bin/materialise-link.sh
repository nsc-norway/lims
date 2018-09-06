#!/bin/bash

set -e

# General script to replace symlink with a copy of the file
while test $# -gt 0
do
	if [[ -e $1.bak ]]
	then 
		echo "ERROR: $1.bak exists"
		exit 1
	fi
	cp $1 $1.bak
	rm $1
	mv $1.bak $1

	shift
done
