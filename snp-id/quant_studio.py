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

    chunks = [all_i_o[i:i+24] for i in xrange(0, len(all_i_o), 24)]
    for file_index, i_o in enumerate(chunks):
        try:
            outfile = Artifact(lims, id=file_ids[file_index])
        except IndexError:
            print "Too many samples. Only", len(file_ids)*24 ,"samples are supported (file:", file_index, ")."
            sys.exit(1)
        rows = []
        header = []

        rows = []
        for xcol in range(16):
            for index, (input, output) in enumerate(i_o, 1):
                sample_no = re.match(r"([0-9]+)-", input.name)
                sample_no = sample_no.group(1) if sample_no else input.name
                rows.append((str(xcol*24 + index), sample_no))

        gs = lims.glsstorage(outfile, 'quant_studio_' + str(file_index+1) + '.txt')
        file_obj = gs.post()
        rows = ["Well\tSample Name"] + ["\t".join(values) for values in rows]
        file_obj.upload("\r\n".join(rows))


main(sys.argv[1], sys.argv[2:])

