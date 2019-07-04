import sys
import re
from genologics import config
from genologics.lims import *

# Script to set default next action, but skip negative control (no default)
# Used for Quant-iT Amplicon QC step
# Second version of the script, supporting to have the Quant-iT as not the
# last step in a protocol (previous version is
# set-complete-protocol-except-neg-control.py).

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    lims.get_batch(Artifact(lims, uri=action['artifact-uri']) for action in step.actions.next_actions if 'artifact-uri' in action)
    if step.configuration.transitions:
        next_step_uri = step.configuration.transitions[0].get("next-step-uri")
        action = "nextstep"
    else:
        action = "complete"
    for next_action in step.actions.next_actions:
        a = Artifact(lims, uri=next_action['artifact-uri'])
        if not re.match(r"16S-\d-neg", a.name):
            if action == "nextstep":
                next_action['step-uri'] = next_step_uri
            next_action['action'] = action
    step.actions.put()

main(process_id=sys.argv[1])

