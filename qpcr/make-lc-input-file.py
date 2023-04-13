import sys
import string
from genologics.lims import *
from genologics import config

# Generates a list of Pos, Sample name, in tab separated format.
#(based on SNP-ID script)

def row_col_index(well):
    row, col = well.split(":")
    return (ord(row) - ord('A'), int(col) - 1)

def main(process_id, file_name_prefix):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    outputs = []
    inputs = []
    for i,o in process.input_output_maps:
        output = o['uri']
        if o and o['output-type'] == 'ResultFile' and o['output-generation-type'] == 'PerInput':
            input = i['uri']
            outputs.append(output)
            inputs.append(input)

    lims.get_batch(inputs + outputs)
    
    name_by_well = {
        output.location[1]: input.name
        for input, output in zip(inputs, outputs)
    }

    if len(set(o.location[0].id for o in outputs)) != 1:
        print(
            "Incorrect number of output containers: {}. Only support one container per run.".format(
            len(set(o.location[0].id for o in outputs)))
        )
        sys.exit(1)

    rows = []
    for orow_index in range(16):
        for ocol_index in range(24):
            sample_name = name_by_well.get("{}:{}".format(string.ascii_uppercase[orow_index], ocol_index), "0")
            output_well_name = "{}{}".format(string.ascii_uppercase[orow_index], ocol_index)
            rows.append("{}\t{}".format(output_well_name, sample_name))

    with open(file_name_prefix + "_LightCycler.txt", "w") as of:
        of.write("Pos\tSample Name\n")
        for row in rows:
            of.write(row + "\n")

main(sys.argv[1], sys.argv[2])

