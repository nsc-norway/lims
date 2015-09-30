import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

def get_buffer_vol(normalised_concentration, input_volume, input_concentration):
    return input_volume * (input_concentration * 1.0 / normalised_concentration - 1.0)


def get_row_key(row):
    container = row[2]
    well = row[3]
    row, col = well.split(":")
    return (container, int(col), row)
    

def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    out_buf = StringIO.StringIO()   

    header = [
            "Pool",
            "Sample",
            "Source cont.",
            "Well",
            "Dest. cont.",
            "Well",
            "Input molarity",
            "Input volume",
            "Normalised molarity",
            "Buffer volume"
            ]


    inputs = []
    outputs = []

    step = Step(lims, id=process.id)

    lims.get_batch(process.all_inputs(unique=True) + process.all_outputs(unique=True))
    lims.get_batch(input.samples[0] for input in process.all_inputs(unique=True))

    update_outputs = set()
    
    rows = []
    for pool in step.pools.pooled_inputs:
        output = pool.output
        dest_container = output.location[0].name
        dest_well = output.location[1]
        for input in pool.inputs:
            sample_name = input.name.encode('utf-8')
            try:
                norm_conc = output.udf['Normalized conc. (nM)']
            except KeyError:
                norm_conc = process.udf['Default pool normalised concentration (nM)']
                output.udf['Normalized conc. (nM)'] = norm_conc
                update_outputs.add(output)
            try:
                input_vol = output.udf['Volume of input']
            except KeyError:
                input_vol = 1 # process.udf['Volume to take from inputs']
                #output.udf['Volume of input'] = input_vol
                #update_outputs.add(output)
         
            input_mol_conc = input.udf['Molarity']
            input_mol_conc_str = "%4.2f" % (input.udf['Molarity'])
            buffer_vol_str = "%4.2f" % (get_buffer_vol(norm_conc, input_vol, input_mol_conc))
            source_container = input.location[0].name
            source_well = input.location[1]
            rows.append([
                pool.name,
                sample_name,
                source_container,
                source_well,
                dest_container,
                dest_well,
                input_mol_conc_str,
                input_vol,
                norm_conc,
                buffer_vol_str
                ])

    if update_outputs:
        lims.put_batch(update_outputs)

    output_file_name = output_file_id + "_normalisation.csv"
    with open(output_file_name, 'wb') as out_file:
        out = csv.writer(out_file)
        out.writerow(header)
        out.writerows(rows)


main(sys.argv[1], sys.argv[2])

