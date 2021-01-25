# Sets reagent labels (indexes) based on a list of indexes in a file
# The file corresponds to a plate.

import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id, index_template_file):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    with open(index_template_file) as f:
        index_data = [l.strip() for l in f.readlines() if l]
        if len(index_data) != 96:
            print("Configuration error: index file does not contain 96 lines.")
            sys.exit(1)
    outputs = process.all_outputs(unique=True, resolve=True)
    for output in outputs:
        if output.type == "Analyte":
            well = output.location[1]
            m = re.match(r"([A-H]):(\d+)")
            if m:
                well_number = "ABCDEFGH".index(m.group(1)) + int(m.group(2))*8
                label = index_data[well_number]
                output.reagent_labels.add(label)
            else:
                print("Error: Well {} does not exist".format(well))
                sys.exit(1)
    lims.put_batch(outputs)

# Use:  main PROCESS-ID INDEX-TEMPLATE-FILE
main(sys.argv[1], sys.argv[2])
