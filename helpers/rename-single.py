# Script to rename a single sample

# Arguments: <NEW_NAME> <SAMPLE_LIMS_ID>

import sys
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

# No point in handling errors, since there's no way to report them...
new_name = sys.argv[1]
analyte_id = sys.argv[2]

analyte = Artifact(lims, id=analyte_id)
analyte.name = new_name
analyte.put()

