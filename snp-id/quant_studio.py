import sys
import re
from genologics.lims import *
from genologics import config

# Generates a list of Well, Sample name, in tab separated format.

def row_col_index(well):
    row, col = well.split(":")
    return (ord(row) - ord('A'), int(col) - 1)

def main(process_id, file_ids):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    inputs = []
    outputs = []
    for i,o in process.input_output_maps:
        output = o['uri']
        if o and o['output-type'] == 'Analyte' and o['output-generation-type'] == 'PerInput':
            input = i['uri']
            inputs.append(input)
            outputs.append(output)

    lims.get_batch(inputs + outputs)
    
    input_by_output_pos = dict(
            (row_col_index(i_o[1].location[1]), i_o[0])
            for i_o in zip(inputs, outputs)
            )

    max_col = max(well[1] for well in input_by_output_pos)

    if len(set(o.container.id for o in outputs)) != 1:
        print "Incorrect number of output containers. Only support one container per run."
        sys.exit(1)

    for file_index, file_id in enumerate(file_ids):
        outfile = Artifact(lims, id=file_id)
        first_col_index = file_index*3 # Each file has 3 columns of output samples (total: 24 samples per file)
        if first_col_index > max_col:
            break
        rows = []
        for ocol_index in range(16): # Total # is 24, but last 8 cols have different placement
            for orow_index in range(16):
                source_row = orow_index // 2
                source_col = (orow_index % 2) + first_col_index
                input = input_by_output_pos.get((source_row, source_col))
                if input:
                    sample_no = re.match(r"([A-Za-z0-9]+)-", input.name)
                    sample_no = sample_no.group(1) if sample_no else input.name
                    well_no = orow_index + ocol_index*16 + 1
                    rows.append((str(well_no), sample_no))

        for ocol_index in range(16,24):
            for orow_index in range(16):
                source_row = "ABCDEFGH"[orow_index // 2]
                source_col = first_col_index + 2
                input = input_by_output_pos.get((source_row, source_col))
                if input:
                    sample_no = re.match(r"([A-Za-z0-9]+)-", input.name)
                    sample_no = sample_no.group(1) if sample_no else input.name
                    well_no = orow_index + ocol_index*16 + 1
                    rows.append((str(well_no), sample_no))
    
        if rows:
            gs = lims.glsstorage(outfile, 'quant_studio_' + str(file_index+1) + '.txt')
            file_obj = gs.post()
            rows = ["Well\tSample Name"] + ["\t".join(values) for values in rows]
            file_obj.upload("\r\n".join(rows))


main(sys.argv[1], sys.argv[2:])

