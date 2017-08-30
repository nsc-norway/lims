import sys
from genologics import config
from genologics.lims import *

# This script uses a custom API function that only exists in the NSC client
# library. It pre-fills the "next action" fields of all the samples with the 
# default next step, or "complete protocol" if it is the last step in a protocol.

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    lims.set_default_next_step(step)

main(sys.argv[1])

