import sys
import re
from genologics.lims import *
from genologics import config

# Generates a list of Well, Sample name, in tab separated format.

def sort_key(elem):
    input, output = elem
    container, well = output.location
    row, col = well.split(":")
    return (container, int(col), row)


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
    
    all_i_o = sorted(zip(inputs, outputs), key=sort_key)
    by_output_pos = dict((i_o[1].location[1], i_o) for i_o in all_i_o)

    if len(set(o.container.id for o in outputs)) != 1:
        print "Incorrect number of output containers. Only support one container per run."
        sys.exit(1)

    for file_index, file_id in enumerate(file_ids):
        outfile = Artifact(lims, id=file_id)
        first_col = 1+file_index*3 # Each file has 3 columns of output samples (total: 24 samples per file)
        rows = []
        for base in range(1, 384, 24):
            for icol, col in enumerate(range(first_col, first_col+3)):
                for irow, row in enumerate("ABCDEFGH"):
                    #for index, (input, output) in enumerate(i_o, 1):
                    i_o = by_output_pos.get("{0}:{1}".format(row, col))
                    if i_o:
                        input, output = i_o
                        sample_no = re.match(r"([0-9]+)-", input.name)
                        sample_no = sample_no.group(1) if sample_no else input.name
                        rows.append((str(base + irow + icol*8), sample_no))
        
        if rows:
            gs = lims.glsstorage(outfile, 'quant_studio_' + str(file_index+1) + '.txt')
            file_obj = gs.post()
            rows = ["Well\tSample Name"] + ["\t".join(values) for values in rows]
            file_obj.upload("\r\n".join(rows))


main(sys.argv[1], sys.argv[2:])

