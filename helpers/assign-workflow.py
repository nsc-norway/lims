# Assign inputs of a given process to workflow

import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id, workflow_name):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    if workflow_name != "None":
        workflows = lims.get_workflows(name=workflow_name)
        if workflows:
            workflow = workflows[0]
            lims.route_analytes(process.all_inputs(unique=True), workflow)
        else:
            print('Error: Workflow "' + str(workflow_name) + '" not found.')
            sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

