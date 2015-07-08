import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

# Setup script for normalisation:
# - Copies UDFs from inputs to outputs

# This script has been reduced to a version of the Genologics 
# copyUDFs function in their ngs-extensions.jar, but I keep it
# because it's faster.

# use:
# python norm-setup.py PROCESS-ID {COPY-UDFs}
# 
# PROCESS-ID: LIMS process ID
# COPY-UDFS:  Any number of UDFs to copy from input to output analytes. Will skip if
#             doesn't exist on source.

def main(process_id, copy_udfs):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    inputs = []
    outputs = []
    for i,o in process.input_output_maps:
        if o and o['output-type'] == 'Analyte' and o['output-generation-type'] == 'PerInput':
            output = o['uri']
            input = i['uri']
            inputs.append(input)
            outputs.append(output)

    lims.get_batch(inputs)
    lims.get_batch(outputs)

    for input, output in zip(inputs, outputs):
        for u in copy_udfs:
            try:
                output.udf[u] = input.udf[u]
            except KeyError:
                pass

    lims.put_batch(outputs)
    

main(sys.argv[1], sys.argv[2:])

