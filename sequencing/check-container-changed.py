# Check that container name is not the default (= LIMSID)

import sys
from genologics.lims import *
from genologics import config


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    flowcells = set(i.location[0] for i in process.analytes())
    if any(fc.name == fc.id for fc in flowcells):
        print "Please make sure container names are changed before continuing."
        sys.exit(1)

main(sys.argv[1])

