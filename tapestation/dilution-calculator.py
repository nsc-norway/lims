import sys
import csv
from genologics.lims import *
from genologics import config

def get_buffer_vol(input):
    molarity = input.udf['Molarity']
    norm_conc = output.udf['Normalized Conc. (nM)']



def main(process_id, output_file_path):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)


    with open(output_file_path) as out_file:
        out = csv.writer(out_file)
        out.writerow(["Project", "Sample name", "Normalised conc", "Buffer Volume"])

        for i,o in process.input_output_maps:
            output = o['uri']
            if o and o['output-type'] == 'ResultFile' and o['output-generation-type'] == 'PerInput': 
                input = i['uri']
                
                


            
    



main(sys.argv[1], sys.argv[2])

