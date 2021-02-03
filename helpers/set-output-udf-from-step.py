import sys
from genologics.lims import *
from genologics import config

# Artifact UDF set script

# Sets UDF on the output analytes to the value of a process-level UDF.

# Argument key_value_pairs:
# The first (0,2,4,....) elements are a the name of a output-level UDF to set, 
# and the second (1,3,5....) elements are the name of the corresponding process-level
# UDF to use as value.

def main(process_id, key_value_pairs):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    outputs = []
    for i,o in process.input_output_maps:
        if o and o['output-type'] == 'Analyte':
            output = o['uri']
            outputs.append(output)

    outputs = lims.get_batch(set(outputs))
    for output in outputs:
        for key,value in zip(key_value_pairs[::2], key_value_pairs[1::2]):
            output.udf[key] = process.udf[value]

    lims.put_batch(outputs)
    

main(sys.argv[1], sys.argv[2:])

