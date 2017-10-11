# This script takes a list of queue-IDs on the command line. For each queue, it 
# takes all artifacts into a step, and pushes them through a step. 

# It is intended to run in a cron job

# It will not work with steps which have output containers (i.e. process types that produce
# outputs which have a location)
# It will work with steps with automatic triggers

import sys
import time
from genologics.lims import *
from genologics import config

def main(qids):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    try:
        lims.check_version()
    except:
        return # If LIMS not reachable then die
    for qid in qids:
        q = Queue(lims, id=qid)
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

if __name__ == "__main__":
    main(sys.argv[1:])

