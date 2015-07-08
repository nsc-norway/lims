import sys
from genologics.lims import *
from genologics import config

# Concentration calculator for qPCR

def calculate_molarity(frag_size, quant_mean):
    return quant_mean * 452.0 / frag_size


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    inputs, measurements = [], []
    for i,o in process.input_output_maps:
        if o and o['output-type'] == 'ResultFile' and o['output-generation-type'] == 'PerInput':
            input = i['uri']
            measurement = o['uri']
            inputs.append(input)
            measurements.append(measurement)

    inputs = lims.get_batch(inputs)
    measurements = lims.get_batch(measurements)

    for input, measurement in zip(inputs, measurements):
        try:
            mol_conc = calculate_molarity(input.udf['Average Fragment Size'], measurement.udf['Quantity mean'])
        except KeyError, e:
            print "Missing ", e, "on", input.name.encode('utf-8')
            sys.exit(1)
        measurement.udf['Molarity'] = mol_conc

    lims.put_batch(measurements)

main(sys.argv[1])

