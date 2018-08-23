import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

# Standard normalisation calculation based on properties of the derived sample
# Used in the library validation protocols. 


def get_buffer_vol(normalised_concentration, input_volume, input_concentration):
    return input_volume * (input_concentration * 1.0 / normalised_concentration - 1.0)


def get_row_key(row):
    container, well = row[0]
    row, _, col = well.partition(':')
    return (container, int(col), row)
    
def get_input_parent_location(artifact):
    pp = artifact.parent_process
    if pp:
        ii = next(i['uri'] for i, o in pp.input_output_maps if o['limsid'] == artifact.id)
    else:
        ii = artifact
    return ii.location

def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    out_buf = StringIO.StringIO()   

    header = [
            "Project",
            "Sample",
            "Prep well",
            "Dest. cont.",
            "Dest. well",
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

    lims.get_batch(inputs + outputs)
    lims.get_batch(input.samples[0] for input in inputs)
    update_outputs = []
    
    data = []
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
        prep_location = get_input_parent_location(input)
        data.append((prep_location,
                [
            project_name,
            sample_name,
            prep_location[1].replace(":", ""),
            dest_container,
            dest_well.replace(":", ""),
            input_mol_conc_str,
            input_vol,
            norm_conc,
            buffer_vol
            ]))

    if update_outputs:
        lims.put_batch(update_outputs)

    rows_sorted = sorted(data, key=get_row_key)

    outputstream = StringIO.StringIO() 
    out = csv.writer(outputstream)
    out.writerow(header)
    out.writerows((out_ro for location, out_ro in rows_sorted))

    output_file_name = "NormalizationSheet.csv"
    outfile = Artifact(lims, id=output_file_id)
    gs = lims.glsstorage(outfile, output_file_name)
    file_obj = gs.post()
    file_obj.upload(outputstream.getvalue())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

