# Check that container name is not the default (= LIMSID)

import sys
from genologics.lims import *
from genologics import config
import re

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    # Not using a batch for the container list because it will almost always be one
    flowcells = set(lims.get_batch(ana.location[0] for ana in lims.get_batch(process.analytes()[0])))
    if len(flowcells) > 1:
        print "There should only be one flow cell in each clustering/denature step."
        sys.exit(1)

    if any(fc.name == fc.id for fc in flowcells):
        print "Please make sure container names are changed before continuing."
        sys.exit(1)

    for fc in flowcells:
        fixed_fcid = fc.name.upper().replace("+", "-")
        if fixed_fcid.startswith("MS") and fixed_fcid.endswith("-50V2"):
            fixed_fcid = fixed_fcid[:-len("-50V2")] + "-050V2"
        if fixed_fcid.startswith("MS"):
            if not re.match(r"MS\d{7}-\d\d\dV\d", fixed_fcid):
                print 'MiSeq reagent cartridge ID has the wrong format.'
                sys.exit(1)
        elif fixed_fcid.startswith("NS"):
            if not re.match(r"NS\d{7}-REAGT", fixed_fcid):
                print ""
                sys.exit(1)
        elif fixed_fcid.startswith("H"):
            if len(fixed_fcid) != 9:
                print "HiSeq flow cell ID should be 9 characters long."
                sys.exit(1)
        else:
            print "The specified value {0} doesn't look like a valid reagent/flow cell ID.".format(fixed_fcid)
            sys.exit(1)

        if fixed_fcid.startswith("RGT"):
            print 'RGT number "' + fc.name + '" shoud not be used as container ID. For MiSeq it should \
                    be MSxxxxx-nnnVn, for HiSeq it is printed on the flow cell package.'
            sys.exit(1)
        if fixed_fcid != fc.name:
            print "Flow cell ID updated to fix user error."
            fc.name = fixed_fcid
            fc.put()

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

