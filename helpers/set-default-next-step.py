import sys
from genologics import config
from genologics.lims import *

# Diag SureSelect workflow

# Copy UDF value from derived sample to sample objects. 
# Used to copy the target concentration into the Sample 

INPUT_UDFNAME = "Normalized conc. (ng/uL)"
OUTPUT_UDFNAME = "Normalized conc. (ng/uL) Diag"

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    outputs = lims.get_batch(Artifact(lims, id=na['artifact-uri']) for na in step.actions.next_actions)
    lims.set_default_next_step(step, outputs)

main(sys.argv[1])

