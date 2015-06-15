# Set the tapestation fragment length

import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id, workflow_name):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    workflows = lims.get_workflows(name=workflow_name)
    workflow = workflows[0]
    lims.route_analytes(process.all_inputs(unique=True), workflow)


main(sys.argv[1], sys.argv[2])

