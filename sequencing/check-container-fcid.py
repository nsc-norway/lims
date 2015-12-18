# Check that container name is not the default (= LIMSID)

import sys
from genologics.lims import *
from genologics import config


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    # analytes() returns tuples ('Output', [Analyte, ...]).
    # Not using a batch for the container list because it will almost always be one
    flowcells = set(lims.get_batch(ana.location[0] for ana in lims.get_batch(process.analytes()[0])))
    if any(fc.name == fc.id for fc in flowcells):
        print "Please make sure container names are changed before continuing."
        sys.exit(1)

    all_known = lims.get_containers(name=(container.name for container in flowcells))
    if len(all_known) > len(flowcells):
        pre_existing = set(all_known) - flowcells
        print "Error: These flowcells already exist in the system:",\
            ", ".join(container.name for container in pre_existing),\
            ". To continue, rename the exising flowcell (or, if in a",\
            "hurry, append \"-NEW\" to the current flowcell and fix it",\
            "later)."
        sys.exit(1)

main(sys.argv[1])

