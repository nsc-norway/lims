# Check that container name is not the default (= LIMSID)

import sys
from genologics.lims import *
from genologics import config
import re

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    # analytes() returns tuples ('Output', [Analyte, ...]).
    # Not using a batch for the container list because it will almost always be one
    flowcells = set(lims.get_batch(ana.location[0] for ana in lims.get_batch(process.analytes()[0])))
    if len(flowcells) > 1:
        print "There should only be one flow cell in each clustering/denature step."
        sys.exit(1)

    if any(fc.name == fc.id for fc in flowcells):
        print "Please make sure container names are changed before continuing."
        sys.exit(1)

    for fc in flowcells:
        if re.match(r"MS.*-\d+v\d$", fc.name):
            print 'Reagent cartridge ID corrected: changed to capital "V".'
            fc.name = fc.name[:-2] + "V" + fc.name[-1:]
            fc.put()
        if fc.name.startswith("MS") and fc.name.endswith("-50V2"):
            fc.name = fc.name[:-len("-50V2")] + "-050V2"
            print 'Reagent cartridge ID corrected: Should be 050V2 for 50 bp kit".'
            fc.put()
        if fc.name.startswith("RGT"):
            print 'RGT number "' + fc.name + '" shoud not be used as container ID. For MiSeq it should \
                    be MSxxxxx-nnnVn, for HiSeq it is printed on the flow cell package.'
            sys.exit(1)

    all_known = lims.get_containers(name=(container.name for container in flowcells))
    if len(all_known) > len(flowcells):
        pre_existing = set(all_known) - flowcells
        print "Error: These flowcells already exist in the system:",\
            ", ".join(container.name for container in pre_existing),\
            ". To continue, rename the exising flowcell in operations interface, or if in a",\
            "hurry, append \"-NEW\" to the current flowcell and fix it",\
            "later."
        sys.exit(1)

main(sys.argv[1])

