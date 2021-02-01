# Sets reagent labels (indexes) based on a column ordered well position
# Labels are sorted by their names. Reagent category is selected based on
# the information in the Step API.

import sys
import re
from genologics.lims import *
from genologics import config

def well_ordinal(well_id):
    row, col = well_id.split(":")
    irow = "ABCDEFGH".index(row)
    icol = int(col)
    return (icol - 1) * 8 + irow

def main(process_id, reagent_label_name_pattern):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    step = Step(lims, id=process_id)
    accept_reagents = sorted([
        (info['name'], reagent)
        for reagent, info in zip(*lims.get_reagent_types(add_info=True))
        if re.match(reagent_label_name_pattern, info['name']) \
                    and reagent.category == step.reagents.reagent_category
        ])
    if len(accept_reagents) != 96:
        print("Something is wrong -- did not find 96 different indexes for '{}'.".format(step.reagents.reagent_category))
        sys.exit(1)
    outputs = lims.get_batch(list(step.reagents.output_reagents))
    if len(set(output.location[0].id for output in outputs)) > 1:
        print("Cannot process multiple containers, include only one plate in the step.")
        sys.exit(1)
    output_ordinal = {output: well_ordinal(output.location[1]) for output in outputs}
    for output in outputs:
        step.reagents.output_reagents[output] = accept_reagents[output_ordinal[output]][0]
    step.reagents.post()

# Use:  main PROCESS-ID Reagent_Label_Name_Pattern
# The purpose of the second argument is to speed up fetching the reagents, by limiting which ones
# will be checked for the right category.
main(sys.argv[1], sys.argv[2])
