# This script sets the default QC flag to PASSED for all ResultFile per input

import sys
from genologics import config
from genologics.lims import *

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    set_outputs = []
    for i, o in process.input_output_maps:
        if o['output-generation-type'] == "PerInput" and o['output-type'] == 'ResultFile':
            o['uri'].qc_flag = "PASSED"
            set_outputs.append(o['uri'])
    lims.put_batch(set_outputs)

main(sys.argv[1])

