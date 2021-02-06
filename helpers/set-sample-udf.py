import sys
from genologics.lims import *
from genologics import config

# Sample UDF set script

# Sets UDF on the samples of all the output analytes to the value provided on the
# command line.

# Argument key_value_pairs:
# The first element is a UDF name and the second is the corresponding UDF value.
# Next, the third element (optional) is another UDF name, then the value follows, etc.

def main(process_id, key_value_pairs):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    inputs = []
    outputs = []
    for i,o in process.input_output_maps:
        if o and o['output-type'] == 'Analyte':
            output = o['uri']
            outputs.append(output)

    lims.get_batch(outputs)
    samples = sum((output.samples for output in outputs), [])
    lims.get_batch(samples)
    for sample in samples:
        for key,value in zip(key_value_pairs[::2], key_value_pairs[1::2]):
            sample.udf[key] = value

    lims.put_batch(samples)
    

main(sys.argv[1], sys.argv[2:])

