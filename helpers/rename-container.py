# Script to rename the container, given an artifact ID in that container

# Arguments: <NEW_NAME> <ARTIFACT_ID>

import sys
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

# No point in handling errors, since there's no way to report them...
new_name = sys.argv[1]
analyte_id = sys.argv[2]

analyte = Artifact(lims, id=analyte_id)
analyte.location[0].name = new_name
analyte.location[0].put()

