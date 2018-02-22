# Check for multiple flow cells
# This is a Python 3 script
import sys
from genologics.lims import *
from genologics import config
import re

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    # analytes() returns tuples ('Output', [Analyte, ...]).
    flowcells = set(ana.location[0] for ana in lims.get_batch(process.analytes()[0]))
    if len(flowcells) > 1:
        print("There should only be one flow cell in each MiSeq Run step, but {0} flow cells found.".format(len(flowcells)))
        sys.exit(1)

main(sys.argv[1])

