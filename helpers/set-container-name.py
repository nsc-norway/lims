# Rename the output containers to a fixed value
import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id, container_name):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    # Warning: This API (selected_containers) has diverged from upstream
    # Need to merge this later.
    containers = lims.get_batch(step.placements.selected_containers)
    for c in containers:
        c.name = container_name
    lims.put_batch(containers)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

