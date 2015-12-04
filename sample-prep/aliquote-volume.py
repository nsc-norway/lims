import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

DEFAULT_QUANTITY = 750


WORKSHEET_HEADER = [
        "Project",
        "Sample",
        "Conc. (ng/uL)",
        "From well",
        "To well",
        "Volume to aliquote (uL)",
        "DNA quantity (ng)"
        ]

ROBOT_HEADER = [
        "SourceBC",
        "SourceWell",
        "DestinationWell",
        "Volume"
        ]

def sort_key(elem):
    input, output, qc = elem
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

    qc_results = lims.get_qc_results(inputs, "Quant-iT QC Diag 1.0")
    lims.get_batch(inputs + outputs + qc_results)
    lims.get_batch(input.samples[0] for sample in inputs)

    rows = []
    updated_outputs = []
    warning = []
    i_o_s_q = zip(inputs, outputs, qc_results)
    for input, output, qc_result in sorted(i_o_s_q, key=sort_key):
        
        # Update the UDF of the output to the default, if it's not set
        try:
            quantity = output.udf['Amount of DNA per sample (ng)']
        except KeyError:
            quantity = DEFAULT_QUANTITY
            output.udf['Amount of DNA per sample (ng)'] = quantity
            updated_outputs.append(output)

        input_conc = qc_result.udf['Concentration']
        volume = quantity * 1.0 / input_conc

        rows.append(ROW[mode](
                input, output, qc_result,
                quantity, volume
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
    


def get_robot_line(input, output, qc_result, quantity, volume):
    return [
            "Hybridisering",
            input.location[1].replace(":",""),
            output.location[1].replace(":", ""),
            volume
            ]

def get_worksheet_line(input, output, qc_result, quantity, volume):
    project_name = input.samples[0].project.name.encode('utf-8')
    sample_name = input.name.encode('utf-8')
    dest_container = output.location[0].name
    dest_well = output.location[1]

    source_container = input.location[0].name
    source_well = input.location[1]

    return [
            project_name,
            sample_name,
            "%4.2f" % qc_result.udf['Concentration'],
            source_well,
            dest_well,
            "%4.2f" % volume,
            "%4.2f" % quantity
            ]



main(*sys.argv[1:4])

