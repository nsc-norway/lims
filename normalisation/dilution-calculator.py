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
    return (container, col, row)
    

def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    out_buf = StringIO.StringIO()   

    header = [
            "Project",
            "Sample name",
            "Dest. container",
            "Well",
            "Input molarity",
            "Input volume",
            "Normalised molarity",
            "Buffer volume"
            ]

    rows = []
    for i,o in process.input_output_maps:
        output = o['uri']
        if o and o['output-type'] == 'Analyte' and o['output-generation-type'] == 'PerInput':
            input = i['uri']
            project_name = input.samples[0].project.name
            sample_name = input.samples[0].name
            dest_container = output.location[0].name
            dest_well = output.location[1]

            norm_conc = output.udf['Normalized conc. (nM)']
            input_vol = output.udf['Volume of input']
            input_conc = input.udf['Molarity']
            buffer_vol = get_buffer_vol(norm_conc, input_vol, input_conc)
            rows.append([
                project_name,
                sample_name,
                dest_container,
                dest_well,
                input_conc,
                input_vol,
                norm_conc,
                buffer_vol
                ])

    rows_sorted = sorted(rows, key=get_row_key)

    output_file_name = output_file_id + "_normalisation.csv"
    with open(output_file_name, 'wb') as out_file:
        out = csv.writer(out_file)
        out.writerow(header)
        out.writerows(rows_sorted)


main(sys.argv[1], sys.argv[2])

