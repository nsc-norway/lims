# Assign inputs of a given process to a workflow with name starting with 
# a specified prefix (not a regular expression, as it has an UDF value as
# its input)

import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id, workflow_prefix):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    if workflow_prefix != "None":
        workflow_data = lims.get_workflows(add_info=True)
        for workflow, info in zip(*workflow_data):
            if info['status'] == "ACTIVE" and info['name'].startswith(workflow_prefix):
                lims.route_analytes(process.all_outputs(unique=True), workflow)
                break
        else: # If not breaked
            print('Error: No workflow matching "' + str(workflow_prefix) + '" was found.')
            sys.exit(1)


if __name__ == "__main__":
    main(process_id=sys.argv[1], workflow_prefix=sys.argv[2])

