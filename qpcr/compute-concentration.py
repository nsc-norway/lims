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

    lims.get_batch(inputs + measurements)
    zeros = []
    for input, measurement in zip(inputs, measurements):
        try:
            frag_size = input.udf['Average Fragment Size']
            if frag_size == 0:
                zeros.append(input.name.encode('utf-8'))
            else:
                mol_conc = calculate_molarity(frag_size, measurement.udf['Quantity mean'])
        except KeyError, e:
            print "Missing ", e, "on", input.name.encode('utf-8')
            sys.exit(1)
        measurement.udf['Molarity'] = mol_conc

    lims.put_batch(measurements)
    if zeros:
        print "These samples have zero fragment size:", ",".join(zeros)
        sys.exit(1)

main(sys.argv[1])

