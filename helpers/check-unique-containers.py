# Assign inputs of a given process to workflow

import sys
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    for placements in step.placements:
        pass # Check it

if __name__ == "__main__":
    main(sys.argv[1])

