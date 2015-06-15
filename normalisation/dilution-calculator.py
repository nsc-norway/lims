import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config


def get_buffer_vol(normalised_concentration, input_volume, input_concentration):
    return input_volume * (input_concentration / normalised_concentration - 1.0)

def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    out_buf = StringIO.StringIO()   

    output_file_name = output_file_id + "_norm.csv"
    with open(output_file_name, 'wb') as out_file:
        out = csv.writer(out_file)
        out.writerow(["Project", "Sample name", "Stock conc", "Stock volume", "Normalised conc", "Buffer volume"])

        for i,o in process.input_output_maps:
            output = o['uri']
            if o and o['output-type'] == 'Analyte' and o['output-generation-type'] == 'PerInput':
                input = i['uri']
                project_name = input.samples[0].project.name
                sample_name = input.samples[0].name

                norm_conc = output.udf['Normalized conc. (nM)']
                input_vol = output.udf['Volume of input']
                input_conc = input.udf['Concentration']
                buffer_vol = get_buffer_vol(norm_conc, input_vol, input_conc)

                out.writerow([project_name, sample_name, input_conc, stock_vol, norm_conc, buffer_vol])


main(sys.argv[1], sys.argv[2])

