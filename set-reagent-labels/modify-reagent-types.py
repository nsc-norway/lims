# Script to rename / modify reagent types.
# Special-purpose script which only handles a specific rename operation, 
# but can be adapted later.

import re
from genologics.lims import *
from genologics import config

def main():
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

    cells = open("xt.txt").read().split()
    sequence_position = dict(
            (sequence, col)
            for col, sequence
            in zip(cells[::2], cells[1::2])
            )

    updated = []
    for reg in lims.get_reagent_types():
        seq_match = re.match(r"SureSelect XT2 Index \d+ \(([ATCG]+)\)", reg.name)
        if seq_match:
            sequence = seq_match.group(1)
            pos = sequence_position[sequence]
            pos_sortable = pos[1:] + "-" + pos[0]
            new_name = "SureSelect XT2 Index %s (%s)" % (pos_sortable, sequence)
            reg.name = new_name
            updated.append(reg)

    for reg in updated:
        print "Updating ", reg.name
        reg.put()

main()

