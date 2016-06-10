import sys
from genologics import config
from genologics.lims import *

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    inputs = Process(lims, id=process_id).all_inputs(resolve=True)
    for i in inputs:
        i.qc_flag = "PASSED"
    lims.put_batch(inputs)

main(sys.argv[1])

