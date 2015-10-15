import sys
from genologics import config
from genologics.lims import *

# Diag SureSelect workflow

# Copy UDF value from derived sample to sample objects. 
# Used to copy the target concentration into the Sample 


def main(process_id, udfname):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    outputs = process.all_outputs(unique=True, resolve=True)
    samples = lims.get_batch(output.samples[0] for output in outputs)
    for output in outputs:
        try:
            output.samples[0].udf[udfname] = output.udf[udfname]
        except KeyError:
            missing.append(output.name)

    if missing:
        print "Missing values for:", ", ".join(missing)
        sys.exit(1)

    lims.put_batch(samples)

main(*sys.argv[1:3])

