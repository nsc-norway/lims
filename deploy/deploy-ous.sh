#!/bin/bash

# Deployment script for LIMS repository for OUS site.
# Deploys the lims and genologics repositories from the dev-lims server to
# ous-lims.
# Arguments: tag to send


( pushd /opt/gls/clarity/customextensions/genologics > /dev/null &&
   git archive $1 &&
   popd > /dev/null &&
   pushd /opt/gls/clarity/customextensions/lims > /dev/null &&
   git archive $1 && 
   popd > /dev/null ) |
   	ssh ous-lims "/bin/bash -c '(pushd /opt/gls/clarity/customextensions > /dev/null &&
	mv genologics genologics.2 &&
	mv lims lims.2 &&
	mkdir genologics lims &&
	cd genologics &&
	tar x &&
	cd ../lims &&
	tar x && 
	cd .. &&
	rm -rf genologics.2 lims.2 )'"


