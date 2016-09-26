# NOTE: This script sets the default QC flag to PASSED, but it also
# sets the monitor flag (feature creep).

import sys
from genologics import config
from genologics.lims import *

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    inputs = process.all_inputs(resolve=True)
    for i in inputs:
        i.qc_flag = "PASSED"
    lims.put_batch(inputs)
    process.udf['Monitor'] = True
    process.put()

main(sys.argv[1])

