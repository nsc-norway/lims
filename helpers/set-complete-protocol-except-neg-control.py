import sys
import re
from genologics import config
from genologics.lims import *

# Script to set default next action, but skip negative control (no default)
# Used for Quant-iT Amplicon QC step

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)

    lims.get_batch(Artifact(lims, uri=action['artifact-uri']) for action in step.actions.next_actions if 'artifact-uri' in action)
    for next_action in step.actions.next_actions:
        if 'artifact-uri' in next_action:
            a = Artifact(lims, uri=next_action['artifact-uri'])
            if not re.match(r"16S-\d-neg", a.name):
                next_action['action'] = "complete"
    step.actions.put()

main(process_id=sys.argv[1])

