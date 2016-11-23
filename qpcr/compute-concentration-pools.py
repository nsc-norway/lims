import sys
from genologics.lims import *
from genologics import config

# Concentration calculator for qPCR

def calculate_molarity(frag_size, quant_mean):
    return quant_mean * 452.0 / frag_size

def get_pool_frag_size(artifact):
    pp = artifact.parent_process
    pool_ios = [i_o for i_o in pp.input_output_maps if i_o[1] == artifact]
    frag_sum = 0.0
    frag_count = len(pool_ios)
    for i_o in pool_ios:
        frag_sum += i_o[0].udf['Average Fragment Size']
    return frag_sum / frag_count


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
        except KeyError, e:
            frag_size = get_pool_frag_size(input)
            
        if frag_size == 0:
            zeros.append(input.name.encode('utf-8'))
        else:
            mol_conc = calculate_molarity(frag_size, measurement.udf['Quantity mean'])
            measurement.udf['Molarity'] = mol_conc

    lims.put_batch(measurements)
    if zeros:
        print "These samples have zero fragment size:", ",".join(zeros)
        sys.exit(1)

main(sys.argv[1])

