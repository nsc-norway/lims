# Assign inputs of a given process to workflow

import sys
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    containers = set(step.placements.get_selected_containers())
    if len(containers) > 1:
        lims.get_batch(containers)
    all_known = lims.get_containers(name=(container.name for container in containers))
    if len(all_known) > len(containers):
        pre_existing = set(all_known) - containers
        print "Containers with these names already exist in the system:",\
                ", ".join(container.name for container in pre_existing)
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1])

