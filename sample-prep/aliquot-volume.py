import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

# Computation for SSXT Aliquot DNA step at the end of PreCapture protocol

MAX_VOL = 30


WORKSHEET_HEADER = [
        "Project",
        "Sample",
        "Conc. (ng/uL)",
        "From well",
        "To well",
        "Volume to aliquot (uL)",
        "DNA quantity (ng)"
        ]

ROBOT_HEADER = [
        "SourceBC",
        "SourceWell",
        "DestinationWell",
        "Volume"
        ]

def sort_key(elem):
    output = elem[1]
    container, well = output.location
    row, col = well.split(":")
    return (container, int(col), row)


def main(process_id, output_file_id, mode):

    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    HEADER = {
            "robot": ROBOT_HEADER,
            "worksheet": WORKSHEET_HEADER
            }

    ROW = {
            "robot": get_robot_line,
            "worksheet": get_worksheet_line
            }

    inputs = []
    outputs = []
    for i,o in process.input_output_maps:
        output = o['uri']
        if o and o['output-type'] == 'Analyte' and o['output-generation-type'] == 'PerInput':
            input = i['uri']
            inputs.append(input)
            outputs.append(output)
    lims.get_batch(inputs + outputs)
    lims.get_batch(input.samples[0] for sample in inputs)

    rows = []
    updated_outputs = []
    warning = []
    i_o_s = zip(inputs, outputs)
    for input, output in sorted(i_o_s, key=sort_key):

        quantity = process.udf['DNA per sample (ng)']
        input_conc = input.udf['Concentration (ng/ul)']
    
        if input_conc <= 0:
            volume = MAX_VOL
        else: 
            volume = min(quantity * 1.0 / input_conc, MAX_VOL)

        rows.append(ROW[mode](
                input, output, quantity, volume
               ))

    lims.put_batch(updated_outputs)

    output_file_name = output_file_id + "_" + mode + ".csv"
    with open(output_file_name, 'wb') as out_file:
        out = csv.writer(out_file)
        out.writerow(HEADER[mode])
        out.writerows(rows)

    if warning:
        print "Warning: too low input concentration for samples:", ", ".join(warning)
        sys.exit(1)
    


def get_robot_line(input, output, quantity, volume):
    return [
            "Hybridisering",
            input.location[1].replace(":",""),
            output.location[1].replace(":", ""),
            volume
            ]

def get_worksheet_line(input, output, quantity, volume):
    project_name = input.samples[0].project.name.encode('utf-8')
    sample_name = input.name.encode('utf-8')
    dest_container = output.location[0].name
    dest_well = output.location[1]

    source_container = input.location[0].name
    source_well = input.location[1]

    return [
            project_name,
            sample_name,
            "%4.2f" % input.udf['Concentration (ng/ul)'],
            source_well,
            dest_well,
            "%4.2f" % volume,
            "%4.2f" % quantity
            ]



main(*sys.argv[1:4])

