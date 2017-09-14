# Assign inputs of a given process to workflow matching (via match()) a regex

import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id, workflow_pattern):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    if workflow_pattern != "None":
        workflow_data = lims.get_workflows(add_info=True)
        for workflow, info in zip(*workflow_data):
            if re.match(workflow_pattern, info['name']):
                lims.route_analytes(process.all_inputs(unique=True), workflow)
                break
        else: # If not breaked
            print('Error: No workflow matching "' + str(workflow_pattern) + '" was found.')
            sys.exit(1)


if __name__ == "__main__":
    main(process_id=sys.argv[1], workflow_pattern=sys.argv[2])

