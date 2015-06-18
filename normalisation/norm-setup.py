import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

# Setup script for normalisation:
# - Copies UDFs from inputs to outputs
# - Sets default normalised concentration and input volume on each output

# use:
# python norm-setup.py PROCESS-ID INPUT-VOL NORM-CONC {COPY-UDFs}
# 
# PROCESS-ID: LIMS process ID
# INPUT-VOL:  Volume to take from inputs
# NORM-CONC:  Desired normalised concentration. If Molarity of input is set, and is
#             less, set the normalized conc field equal to the Molarity.
# COPY-UDFS:  Any number of UDFs to copy from input to output analytes. Will skip if
#             doesn't exist on source.

def main(process_id, input_vol, norm_conc, copy_udfs):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    input_vol_float = float(input_vol)
    norm_conc_float = float(norm_conc)
    
    for i,o in process.input_output_maps:
        if o and o['output-type'] == 'Analyte' and o['output-generation-type'] == 'PerInput':
            output = o['uri']
            input = i['uri']
            output.get()
            try:
                source_molarity = input.udf['Molarity']
                output.udf['Normalized conc. (nM)'] = min(norm_conc_float, source_molarity)
            except KeyError:
                output.udf['Normalized conc. (nM)'] = norm_conc_float
            output.udf['Volume of input'] = input_vol_float
            for u in copy_udfs:
                try:
                    output.udf[u] = input.udf[u]
                except KeyError:
                    pass
            output.put()

main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])

