# Assign to demultiplexing workflow and start a step

import sys
import re
import time
from genologics.lims import *
from genologics import config

def start_step(lims, analytes, workflow):
    protocol = workflow.protocols[0]
    ps = protocol.steps[0]
    queue = ps.queue()
    for attempt in range(3):
        if set(analytes) <= set(queue.artifacts):
            lims.create_step(ps, analytes)
            break
        else:
            time.sleep(1)
            queue.get(force=True)


def main(process_id, workflow_name):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    # Sequencing process
    process = Process(lims, id=process_id)
    workflows = lims.get_workflows(name=workflow_name)
    workflow = workflows[0]
    analytes = process.all_inputs(unique=True)
    lims.route_analytes(analytes, workflow)
    start_step(lims, analytes, workflow)

main(*sys.argv[1:])

