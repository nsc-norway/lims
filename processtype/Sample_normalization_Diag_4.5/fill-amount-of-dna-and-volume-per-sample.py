import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id, concentration_source):
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
    samples = [input.samples[0] for input in inputs]
    lims.get_batch(samples)

    if concentration_source == "sample":
        concentrations = [sample.udf.get('Sample conc. (ng/ul)') for sample in samples]
    else:
        concentrations = [input.udf.get('Concentration (ng/ul)') for input in inputs]

    missing_udf = [input.name for input, conc in zip(inputs, concentrations) if conc is None]
    if missing_udf:
        print "Error: input concentration not known for sample(s)", ", ".join(missing_udf)
        sys.exit(1)
    
    i_o_s = zip(inputs, outputs, samples, concentrations)
    for input, output, sample, input_conc in i_o_s:
        
        # volume
        output.udf['Volume (uL) WatchMaker'] = 40
        # amount of DNA
        if input_conc >= 20:
            output.udf['Amount of DNA per sample (ng) WatchMaker'] = 200
        else:
            output.udf['Amount of DNA per sample (ng) WatchMaker'] = 75

    lims.put_batch(outputs)


main(process_id=sys.argv[1], concentration_source=sys.argv[2])
