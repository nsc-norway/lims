# Script to list the names of indexes. Useful when deleting indexes, then this
# list can be used for the blacklist

import re
from genologics.lims import *
from genologics import config

def main():
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

    matches = []
    
    reagent_types = lims.get_reagent_types()
    for reg in reagent_types:
        match = re.match(r"N7\d\d-E5\d\d \([ATCG]+-[ATCG]+\)", reg.name)
        if match:
            matches.append(reg.id)

    print "Scanned a total of", len(reagent_types), "indexes."
    print "Found", len(matches), "indexes:"
    print matches

main()

