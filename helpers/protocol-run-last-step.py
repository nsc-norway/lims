# Script to run a protocol step automatically (e.g. "Finish protocol")

# This script takes an exact protocol name on the command line. See also 
# workflow-run-last-step.py for a script for workflows, with a pattern instead of 
# an exact match.

# It is intended to run in a cron job

# It will find all artifacts in the queue, and run a step with them automatically, selecting the
# default next step.


import sys
import re
import time
from genologics.lims import *
from genologics import config

def main(protocol_name):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    try:
        lims.check_version()
    except:
        return # If LIMS not reachable then die
    try:
        protocol = next(iter(lims.get_protocols(name=protocol_name)))
    except StopIteration:
        print "Protocol", protocol_name, "not found."
        sys.exit(1)
    errors = 0
    q = protocol.steps[-1].queue()
    if q.artifacts:
        step = lims.create_step(q.protocol_step_config, q.artifacts)
        while step.current_state.upper() != "COMPLETED":
            if step.current_state == "Assign Next Steps":
                lims.set_default_next_step(step)
            if not step.program_status or step.program_status.status not in ["QUEUED", "RUNNING"]:
                try:
                    step.advance()
                except:
                    errors += 1
                    if errors == 5:
                        print "Too many errors trying to advance step"
                        sys.exit(1)
            time.sleep(0.5)
            step.get(force=True)
            if step.program_status:
                step.program_status.get(force=True)

if __name__ == "__main__":
    main(protocol_name=sys.argv[1]) 
