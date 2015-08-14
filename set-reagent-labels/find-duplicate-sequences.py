import sys

from genologics.lims import *
from genologics import config

from collections import defaultdict

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)


reagent_types = lims.get_reagent_types()

print "Processing reagent types..."

seq_rts = defaultdict(list)

for reagent_type in reagent_types:
    seq_rts[reagent_type.index_sequence].append(reagent_type)

for dupes in (rts for sequence, rts in seq_rts.items() if len(rts) > 1):
    print "-------", len(dupes), "dupes", "-------"
    for dup in dupes:
        print dup.name

    print""
else:
    print "No dupes found!"

