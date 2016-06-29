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


def main(process_id, file_id):
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
    
    rows = []
    header = []
    i_o = zip(inputs, outputs)

    if len(i_o) > 24:
        print "Too many samples. Only 24 samples are supported."
        sys.exit(1)

    rows = []
    for xcol in range(16):
        for index, (input, output) in enumerate(sorted(i_o, key=sort_key), 1):
            sample_no = re.match(r"([0-9]+)-", input.name)
            sample_no = sample_no.group(1) if sample_no else input.name
            rows.append((str(xcol*24 + index), sample_no))

    outfile = Artifact(lims, id=file_id)
    gs = lims.glsstorage(outfile, 'quant_studio.txt')
    file_obj = gs.post()
    rows = ["Well\tSample Name"] + ["\t".join(values) for values in rows]
    file_obj.upload("\n".join(rows))


main(sys.argv[1], sys.argv[2])

