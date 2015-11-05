import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

DEFAULT_QUANTITY = 750

def sort_key(elem):
    input, output, sample, qc = elem
    container, well = output.location
    row, col = well.split(":")
    return (container, int(col), row)

def get_qc_results(lims, analytes, qc_process_name):
    limsids = [a.id for a in analytes]
    qc_processes = lims.get_processes(inputartifactlimsid=limsids, type=qc_process_name)

    qc_results = {}
    # Uses most recent QC result for each sample
    for qc_process in sorted(qc_processes, key=lambda x: x.date_run):
        for i, o in qc_process.input_output_maps:
            if o and o['output-type'] == "ResultFile" and o['output-generation-type'] == 'PerInput':
                qc_results[i['uri']] = o['uri']

    return [qc_results[a] for a in analytes]
    

def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    out_buf = StringIO.StringIO()   

    header = [
            "Project",
            "Sample",
            "Conc. (ng/uL)",
            "From well",
            "To well",
            "Volume to aliquote (uL)",
            "DNA quantity (ng)"
            ]

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
    qc_results = get_qc_results(lims, inputs, "Quant-iT QC Diag 1.0")

    updated_outputs = []
    warning = []
    rows = []
    i_o_s_q = zip(inputs, outputs, samples, qc_results)
    for input, output, sample, qc_result in sorted(i_o_s_q, key=sort_key):
        project_name = input.samples[0].project.name.encode('utf-8')
        sample_name = input.name.encode('utf-8')
        dest_container = output.location[0].name
        dest_well = output.location[1]

        try:
            norm_mass = output.udf['Normalized amount of DNA (ng)']
        except KeyError:
            norm_mass = DEFAULT_QUANTITY
            output.udf['Normalized amount of DNA (ng)'] = norm_mass
            updated_outputs.append(output)

        input_conc = qc_result.udf['Concentration']
        sample_volume = norm_mass * 1.0 / input_conc

        source_container = input.location[0].name
        source_well = input.location[1]

        rows.append([
            project_name,
            sample_name,
            "%4.2f" % input_conc,
            source_well,
            dest_well,
            "%4.2f" % sample_volume,
            "%4.2f" % norm_mass
            ])

    lims.put_batch(updated_outputs)

    output_file_name = output_file_id + "_aliquote.csv"
    with open(output_file_name, 'wb') as out_file:
        out = csv.writer(out_file)
        out.writerow(header)
        out.writerows(rows)

    if warning:
        print "Warning: too low input concentration for samples:", ", ".join(warning)
        sys.exit(1)

main(sys.argv[1], sys.argv[2])

