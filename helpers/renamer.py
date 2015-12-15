# Name correction script. To be run on the project dashboard. 
# Sets the name of each analyte to the name of the submitted
# sample.

import sys
from genologics.lims import *
from genologics import config

def main(artifact_ids):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    analytes = lims.get_batch(Artifact(lims, id=artifact_id) for artifact_id in artifact_ids)
    for analyte in analytes:
        if len(analyte.samples) == 1:
            analyte.name = analyte.samples[0].name
        else:
            print "Invalid number of samples for", analyte.name
            sys.exit(1)
    lims.put_batch(analytes)

if __name__ == "__main__":
    main(sys.argv[1:])

