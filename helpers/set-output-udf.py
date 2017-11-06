import sys
from genologics.lims import *
from genologics import config

# Artifact UDF set script

# Sets UDF on the output analytes to the value provided on the
# command line.

# Argument key_value_pairs:
# The first element is a UDF name and the second is the corresponding UDF value.
# Next, the third element (optional) is another UDF name, then the value follows, etc.

def main(process_id, key_value_pairs):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    outputs = []
    for i,o in process.input_output_maps:
        if o and o['output-type'] == 'Analyte' and o['output-generation-type'] == 'PerInput':
            output = o['uri']
            outputs.append(output)

    lims.get_batch(outputs)
    for output in outputs:
        for key,value in zip(key_value_pairs[::2], key_value_pairs[1::2]):
            output.udf[key] = value

    lims.put_batch(output)
    

main(sys.argv[1], sys.argv[2:])

