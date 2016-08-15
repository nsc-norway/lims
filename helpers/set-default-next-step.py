import sys
from genologics import config
from genologics.lims import *

# Diag SureSelect workflow

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    lims.set_default_next_step(step)

main(sys.argv[1])

