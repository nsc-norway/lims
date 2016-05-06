#!/bin/bash -e

# Deployment script for LIMS repository for CEES site.
# Deploys the lims and genologics repositories from the local repository to
# cees-lims.
# Arguments: tag to send

( pushd ../../genologics > /dev/null &&
   git archive $1 &&
   popd > /dev/null &&
   pushd .. > /dev/null &&
   git archive $1 && 
   popd > /dev/null ) |
   	ssh cees-lims.sequencing.uio.no "/bin/bash -c '(pushd /opt/gls/clarity/customextensions > /dev/null &&
	mv genologics genologics.2 &&
	mv lims lims.2 &&
	mkdir genologics lims &&
	cd genologics &&
	tar x &&
	cd ../lims &&
	tar x && 
	sed -i  \"s/^SITE=\\\"TESTING\\\"$/SITE=\\\"cees\\\"/\" monitor/main.py &&
	cd .. &&
	rm -rf genologics.2 lims.2
	rsync -rl genologics lims /var/www/html/ )'"


