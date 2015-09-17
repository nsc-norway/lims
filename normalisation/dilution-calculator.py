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
    show_source = process.udf['Show source location']

    out_buf = StringIO.StringIO()   

    if show_source:
        header = [
                "Project",
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
    else:
        header = [
                "Project",
                "Sample",
                "Dest. cont."
                "Well",
                "Input molarity",
                "Input volume",
                "Normalised molarity",
                "Buffer volume"
                ]


    inputs = []
    outputs = []
    for i,o in process.input_output_maps:
        output = o['uri']
        if o and o['output-type'] == 'Analyte' and o['output-generation-type'] == 'PerInput':
            input = i['uri']
            inputs.append(input)
            outputs.append(output)

    lims.get_batch(inputs)
    lims.get_batch(input.samples[0] for input in inputs)
    lims.get_batch(outputs)
    update_outputs = []
    
    rows = []
    for input, output in zip(inputs, outputs):
        project_name = input.samples[0].project.name.encode('utf-8')
        sample_name = input.name.encode('utf-8')
        dest_container = output.location[0].name
        dest_well = output.location[1]

        update_output = False
        try:
            norm_conc = output.udf['Normalized conc. (nM)']
        except KeyError:
            norm_conc = process.udf['Default normalised concentration (nM)']
            output.udf['Normalized conc. (nM)'] = norm_conc
            update_output = True
        try:
            input_vol = output.udf['Volume of input']
        except KeyError:
            input_vol = process.udf['Volume to take from inputs']
            output.udf['Volume of input'] = input_vol
            update_output = True
        if update_output:
            update_outputs.append(output)
         
        input_mol_conc = input.udf['Molarity']
        input_mol_conc_str = "%4.2f" % (input.udf['Molarity'])
        buffer_vol = "%4.2f" % (get_buffer_vol(norm_conc, input_vol, input_mol_conc))
        if show_source:
            source_container = input.location[0].name
            source_well = input.location[1]
            rows.append([
                project_name,
                sample_name,
                source_container,
                source_well,
                dest_container,
                dest_well,
                input_mol_conc_str,
                input_vol,
                norm_conc,
                buffer_vol
                ])
        else:
            rows.append([
                project_name,
                sample_name,
                dest_container,
                dest_well,
                input_mol_conc_str,
                input_vol,
                norm_conc,
                buffer_vol
                ])

    lims.put_batch(update_outputs)

    rows_sorted = sorted(rows, key=get_row_key)

    output_file_name = output_file_id + "_normalisation.csv"
    with open(output_file_name, 'wb') as out_file:
        out = csv.writer(out_file)
        out.writerow(header)
        out.writerows(rows_sorted)


main(sys.argv[1], sys.argv[2])

