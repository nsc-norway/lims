import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

def sort_key(elem):
    input, output, sample = elem
    container, well = output.location
    row, col = well.split(":")
    return (container, int(col), row)


def main(process_id, config):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    out_buf = StringIO.StringIO()   

    inputs = []
    outputs = []
    for i,o in process.input_output_maps:
        output = o['uri']
        if o and o['output-type'] == 'Analyte' and o['output-generation-type'] == 'PerInput':
            input = i['uri']
            inputs.append(input)
            outputs.append(output)

    lims.get_batch(inputs + outputs)
    if config == "norm1":
        samples = [input.samples[0] for input in inputs]
        lims.get_batch(samples)
        concentrations = [sample.udf.get('Sample conc. (ng/ul)') for sample in samples]
        print concentrations
    elif config == "norm2":
        try:
            qc_results = lims.get_qc_results(inputs, "Quant-iT QC (low conc.) Diag 1.1")
        except KeyError, e:
            print "Missing QC result for", e
            sys.exit(1)
        concentrations = [result.udf.get('Concentration') for result in qc_results]
    else:
        concentrations = [None]*len(inputs)

    if config in ["norm1", "norm2"]:
        missing_udf = [input.name for input, conc in zip(inputs, concentrations) if conc is None]
        if missing_udf:
            print "Error: input concentration not known for samples", ", ".join(missing_udf)
            sys.exit(1)
    
    updated_outputs = set()
    warning = []
    missing_udf = []
    rows = []
    i_o_s = zip(inputs, outputs, concentrations)
    for index, (input, output, input_conc) in enumerate(sorted(i_o_s, key=sort_key)):
        sample_name = input.name.encode('utf-8')
        dest_container = output.location[0].name
        dest_well = output.location[1].replace(":", "")
        try:
            norm_conc = output.udf['Normalized conc. (ng/uL)']
        except KeyError:
            norm_conc = process.udf['Default normalized conc. (ng/uL)']
            output.udf['Normalized conc. (ng/uL)'] = norm_conc
            updated_outputs.add(output)
        try:
            output_vol = output.udf['Volume (uL)']
        except KeyError:
            output_vol = process.udf['Default volume (uL)']
            output.udf['Volume (uL)'] = output_vol
            updated_outputs.add(output)

        sample_volume = (norm_conc * 1.0 / input_conc) * output_vol
        buffer_volume = output_vol - sample_volume

        row = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

        well = "%s:%d" % (row[index % 12], (index // 12) + 1)
        well_2base = "%s:%d" % (row[index % 12], (index // 12) + 2)

        columns = [
                ("Prove", re.match(r"([0-9]+)-")),
                ("DNA_Rack_pos", "DNA_%d" % (index // 24 + 1)),
                ("Pos_i_DNA_Rack", str((index % 24) + 1)),
                ("Destinasjon", "Fortynning_1"),
                ("Pos_i_Fortynning_1", well),
                ("DNA_Kons", input_conc),
                ("DNA_Vol", TODO),
                ("TE_pos", "TE"),
                ("TE_bronn", "1"),
                ("TE_til_Fortynning_1_pos", well),
                ("TE_vol", buffer_volume),
                ("Quant-it_miks_pos", "Quant-it_miks"),
                ("Quant-it_miks_bronn", "1"),
                ("Destinasjon2", "Quant-it_plate"),
                ("Quant-it_plate_bronn", well_2base),
                ("Quant-it_miks_vol", "200"),
                ("Fortynning1_pos", "Fortynning_1"),
                ("Pos_i_Fortynning1_2", well),
                ("Destinasjon3", "Quant-it_plate"),
                ("Quant-it_bronn2", well_2base),
                ("Vol_fortDNA", "1.2")
            ]

        header = [x[0] for x in columns]


        if buffer_volume < 0:
            warning.append(output.name)
            buffer_volume = 0
            sample_volume = output_vol
            warning.append(output.name)




    lims.put_batch(updated_outputs)

    out_buffer = StringIO.StringIO()
    out = csv.writer(out_buffer)
    out.writerow(header)
    out.writerows(rows)

    outfiles = set((o['uri'] for i, o in process.input_output_maps if o['output-generation-type'] == "PerAllInputs"))
    if len(outfiles) == 0:
        print "No output file was configured"
        sys.exit(1)
    elif len(outfiles) > 1:
        print "Too many output files were configured"
        sys.exit(1)

    gs = lims.glsstorage(outfiles.pop(), 'biomek-fortynning.csv')
    file_obj = gs.post()
    file_obj.upload(out_buffer.getvalue())

    if warning:
        print "Warning: too low input concentration for samples:", ", ".join(warning), "."
        sys.exit(1)

# Use:  PROCESS_ID CONFIG={"norm1"|"norm2"}
main(sys.argv[1], sys.argv[2])

