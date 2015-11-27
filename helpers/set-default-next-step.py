import sys
from genologics import config
from genologics.lims import *

# Diag SureSelect workflow

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    outputs = lims.get_batch(Artifact(lims, id=na['artifact-uri']) for na in step.actions.next_actions)
    lims.set_default_next_step(step, outputs)

main(sys.argv[1])

