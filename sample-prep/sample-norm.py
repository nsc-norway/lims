import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

def sort_key(elem):
    input, output, sample = elem
    container, well = input.location
    row, col = well.split(":")
    return (container, int(col), row)
    

def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    out_buf = StringIO.StringIO()   

    header = [
            "Project",
            "Sample",
            "Sample conc.",
            "From well",
            "To well",
            "Sample volume",
            "Buffer volume",
            "Normalised conc.",
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

    updated_outputs = []
    
    warning = []
    rows = []
    i_o_s = zip(inputs, outputs, samples)
    for input, output, sample in sorted(i_o_s, key=sort_key):
        project_name = input.samples[0].project.name.encode('utf-8')
        sample_name = input.name.encode('utf-8')
        dest_container = output.location[0].name
        dest_well = output.location[1]

        try:
            norm_conc = output.udf['Normalized conc. (ng/uL)']
        except KeyError:
            print "Missing value for Normalized conc. (ng/uL) on", output.name, "(and possibly others)"
            sys.exit(1)
        try:
            output_vol = output.udf['Volume (uL)']
        except KeyError:
            print "Missing value for Volume (uL) on", output.name, "(and possibly others)"
            sys.exit(1)
         
        input_conc = sample.udf['Sample conc. (ng/ul)']
        sample_volume = norm_conc * output_vol / input_conc
        buffer_volume = output_vol - sample_volume

        if buffer_volume < 0:
            warning.append(output.name)

        source_container = input.location[0].name
        source_well = input.location[1]

        rows.append([
            project_name,
            sample_name,
            input_conc,
            source_well,
            dest_well,
            "%4.2f" % sample_volume,
            "%4.2f" % buffer_volume,
            "%4.2f" % norm_conc
            ])

    output_file_name = output_file_id + "_norm.csv"
    with open(output_file_name, 'wb') as out_file:
        out = csv.writer(out_file)
        out.writerow(header)
        out.writerows(rows)

    if warning:
        print "Warning: too low input concentration for samples:", ", ".join(warning)
        sys.exit(1)

main(sys.argv[1], sys.argv[2])

