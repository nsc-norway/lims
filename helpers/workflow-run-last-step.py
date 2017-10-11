# This script takes a pattern to match a workflow name on the command line. 
# It finds the queue of the last stage of the workflow, takes all artifacts in that
# queue into a step, and pushes them through the step. 

# It is intended to run in a cron job

# It will not work with steps which have output containers (i.e. process types that produce
# outputs which have a location)
# It will work with steps with automatic triggers

import sys
import re
import time
from genologics.lims import *
from genologics import config

def main(workflow_pattern):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    try:
        lims.check_version()
    except:
        return # If LIMS not reachable then die
    workflow_data = lims.get_workflows(add_info=True)
    for workflow, info in zip(*workflow_data):
        if info['status'] == "ACTIVE" and re.match(workflow_pattern, info['name']):
            q = workflow.stages[-1].step.queue()
            if q.artifacts:
                step = lims.create_step(q.protocol_step_config, q.artifacts)
                while step.current_state.upper() != "COMPLETED":
                    if step.current_state == "Assign Next Steps":
                        lims.set_default_next_step(step)
                    if not step.program_status or step.program_status.status not in ["QUEUED", "RUNNING"]:
                        step.advance()
                    time.sleep(0.5)
                    step.get(force=True)
                    if step.program_status:
                        step.program_status.get(force=True)
            break

if __name__ == "__main__":
    main(workflow_pattern=sys.argv[1])

