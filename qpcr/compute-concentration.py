import sys
from genologics.lims import *
from genologics import config

# Concentration calculator for qPCR

def calculate_conc(frag_size, quant_mean):
    return quant_mean * 103.0 / frag_size


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    inputs = process.all_inputs(unique=True)
    for input in inputs:
        input.get()
        conc = calculate_conc(input.udf['Average Fragment Size'], input.udf['Quantity mean'])
        input.udf['Concentration'] = conc
        input.put()


main(sys.argv[1])

