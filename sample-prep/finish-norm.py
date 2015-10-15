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
    # We need the next actions anyway, so get the list of outputs from the
    # next actions resource
    outputs = lims.get_batch(Artifact(lims, id=na['artifact-uri']) for na in step.actions.next_actions)
    samples = lims.get_batch(output.samples[0] for output in outputs)
    missing = []
    for output in outputs:
        try:
            output.samples[0].udf[OUTPUT_UDFNAME] = output.udf[INPUT_UDFNAME]
        except KeyError:
            missing.append(output.name)

    if missing:
        print "Missing values for:", ", ".join(missing)
        sys.exit(1)

    lims.put_batch(samples)
    lims.set_default_next_step(step, outputs)

main(sys.argv[1])
