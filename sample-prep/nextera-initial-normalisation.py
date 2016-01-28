import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

DEFAULT_OUTPUT_VOL = 10 # uL
DEFAULT_OUTPUT_CONC = 10  # ng/uL

def sort_key(elem):
    input, output, sample = elem
    container, well = output.location
    row, col = well.split(":")
    return (container, int(col), row)

def worksheet_line():
    pass

def robot_line():
    pass
    

def main(process_id, output_file_id, file_type):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    out_buf = StringIO.StringIO()   

    if file_type == "robot":
        header = [
                "Project",
                "Sample",
                "Sample conc.",
                "From well",
                "To well",
                "Sample volume",
                "Buffer volume",
                "Norm. conc."
                ]
    else:
        header = [
                "FromWell",
                "ToWell",
                "Sample volume",
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

    lims.get_batch(inputs + outputs)
    samples = [input.samples[0] for input in inputs]
    lims.get_batch(samples)

    updated_outputs = set()
    
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
            norm_conc = DEFAULT_OUTPUT_CONC
            output.udf['Normalized conc. (ng/uL)'] = norm_conc
            updated_outputs.add(output)
        try:
            output_vol = output.udf['Volume (uL)']
        except KeyError:
            output_vol = DEFAULT_OUTPUT_VOL
            output.udf['Volume (uL)'] = output_vol
            updated_outputs.add(output)
         
        try:
            input_conc = sample.udf['Sample conc. (ng/ul)']
        except KeyError:
            print "Error: input concentration not known for sample", sample.name
            sys.exit(1)

        sample_volume = (norm_conc / input_conc) * output_vol
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

    lims.put_batch(updated_outputs)

    output_file_name = output_file_id + "_norm.csv"
    with open(output_file_name, 'wb') as out_file:
        out = csv.writer(out_file)
        out.writerow(header)
        out.writerows(rows)

    if warning:
        print "Warning: too low input concentration for samples:", ", ".join(warning)
        sys.exit(1)

# Use:  PROCESS_ID OUTPUT_FILE_ID FILE_FORMAT
main(sys.argv[1], sys.argv[2], sys.argv[3])

