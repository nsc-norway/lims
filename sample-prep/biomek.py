import sys
import csv
import re
import StringIO
from genologics.lims import *
from genologics import config

# This is just a CSV file generator, for use with the Biomek robots.
# Two normalisation steps for Nextera are supported by this one script.

def sort_key(elem):
    input, output, sample = elem
    container, well = output.location
    row, col = well.split(":")
    return (container, int(col), row)


def main(process_id, filecfg, file_id, norm_conc, vol):
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
    if filecfg == "norm1":
        samples = [input.samples[0] for input in inputs]
        lims.get_batch(samples)
        concentrations = [sample.udf.get('Sample conc. (ng/ul)') for sample in samples]
    elif filecfg == "norm2":
        try:
            qc_results = lims.get_qc_results_re(inputs, r"Quant-iT QC.*")
        except KeyError, e:
            print "Missing QC result for", e
            sys.exit(1)
        concentrations = [result.udf.get('Concentration') for result in qc_results]
    else:
        concentrations = [None]*len(inputs)

    if filecfg in ["norm1", "norm2"]:
        missing_udf = [input.name for input, conc in zip(inputs, concentrations) if conc is None]
        if missing_udf:
            print "Error: input concentration not known for samples", ", ".join(missing_udf)
            sys.exit(1)
    
    warning = []
    missing_udf = []
    rows = []
    header = []
    i_o_s = zip(inputs, outputs, concentrations)
    for index, (input, output, input_conc) in enumerate(sorted(i_o_s, key=sort_key)):
        sample_name = input.name.encode('utf-8')

        row = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

        well = "%s%d" % (row[index % 8], (index // 8) + 1)
        well_2base = "%s%d" % (row[index % 8], (index // 8) + 2)

        sample_no = re.match(r"([0-9]+)-", sample_name)
        if filecfg == "norm1":
            # (20 ng/uL * 25 uL) / conc = (500 ng) / conc
            sample_volume = (norm_conc * vol * 1.0 / input_conc)
            buffer_volume = vol - sample_volume

            if buffer_volume < 0:
                buffer_volume = 0.0
                sample_volume = vol
                warning.append(output.name)
            columns = [
                    ("Prove", sample_no.group(1) if sample_no else sample_name),
                    ("DNA_Rack_pos", "DNA_%d" % (index // 24 + 1)),
                    ("Pos_i_DNA_Rack", str((index % 24) + 1)),
                    ("Destinasjon", "Fortynning_1"),
                    ("Pos_i_Fortynning_1", well),
                    ("DNA_Kons", input_conc),
                    ("DNA_Vol", sample_volume),
                    ("TE_pos", "TE"),
                    ("TE_bronn", "1"),
                    ("TE_til_Fortynning_1_pos", well),
                    ("TE_vol", buffer_volume),
                    ("Quant-it_miks_pos", "Quant-it_miks"),
                    ("Quant-it_miks_bronn", "1"),
                    ("Destinasjon2", "Quant-it_plate"),
                    ("Quant-it_plate_bronn", well_2base),
                    ("Quant-it_miks_vol", "200"),
                ]
            output.udf['Normalized conc. (ng/uL)'] = norm_conc
            output.udf['Volume (uL)'] = vol

        elif filecfg == "norm2":
            sample_volume = (norm_conc * vol * 1.0 / input_conc)
            buffer_volume = vol - sample_volume 

            if buffer_volume < 0:
                buffer_volume = 0.0
                sample_volume = vol
                warning.append(output.name)
            columns = [
                    ("TE_pos", "TE"),
                    ("TE_bronn", "1"),
                    ("TE_vol", buffer_volume),

                    ("Fortynning_2_pos", "Fortynning_2"),
                    ("Fortynning_2_bronn", well),

                    ("Prove", sample_no.group(1) if sample_no else sample_name),

                    ("Fortynning_1_pos", "Fortynning_1"),
                    ("Fortynning_1_bronn", well),

                    ("DNAfort_kons", input_conc),

                    ("Fortynning_1_vol", sample_volume),
                ]

            output.udf['Normalized conc. (ng/uL)'] = norm_conc
            output.udf['Volume (uL)'] = vol


        if not header:
            header = [x[0] for x in columns]

        rows.append([x[1] for x in columns])


    lims.put_batch(outputs)

    out_buffer = StringIO.StringIO()
    out = csv.writer(out_buffer)
    out.writerow(header)
    out.writerows(rows)

    outfile = Artifact(lims, id=file_id)
    if filecfg == "norm1":
        filename = "biomek-fortynning.csv"
    elif filecfg == "norm2":
        filename = "biomek-fortynning2.csv"
    else:
        filename = "UNKNOWN.csv"
    gs = lims.glsstorage(outfile, filename)
    file_obj = gs.post()
    file_obj.upload(out_buffer.getvalue())

    if warning:
        print "Warning: too low input concentration for samples:", ", ".join(warning), "."
        sys.exit(1)

# Use:  main PROCESS_ID TYPE FILEID CONCENTRATION VOLUME
main(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]))

