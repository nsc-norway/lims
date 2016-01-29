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

def worksheet_line():
    pass

def robot_line():
    pass
    

def main(process_id, output_file_id, concentration_source):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    out_buf = StringIO.StringIO()   

    header = [
            "Prove",
            "BufferPosisjon",
            "BufferBronn",
            "96-plate",
            "Bronn_Posisjon_96plate",
            "Rack_Pos_DNAror",
            "Pos_i_rack_DNA",
            "DNA_Kons",
            "DNA_Vol",
            "Buffer_Vol",
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
    if concentration_source == "sample":
        samples = [input.samples[0] for input in inputs]
        lims.get_batch(samples)
        concentrations = [sample.udf.get('Sample conc. (ng/ul)') for sample in samples]
        print concentrations
    elif concentration_source == "quantit":
        try:
            qc_results = lims.get_qc_results(inputs, "Quant-iT QC Diag 1.0")
        except KeyError, e:
            print "Missing QC result for", e
            sys.exit(1)
        concentrations = [result.udf.get('Concentration') for result in qc_results]

    missing_udf = [input.name for input, conc in zip(inputs, concentrations) if conc is None]
    if missing_udf:
        print "Error: input concentration not known for samples", ", ".join(missing_udf)
        sys.exit(1)
    
    updated_outputs = set()
    warning = []
    missing_udf = []
    rows = []
    i_o_s = zip(inputs, outputs, concentrations)
    for input, output, input_conc in sorted(i_o_s, key=sort_key):
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

        if buffer_volume < 0:
            warning.append(output.name)
            buffer_volume = 0
            sample_volume = output_vol
            warning.append(output.name)

        source_container = input.location[0].name
        source_well = input.location[1]

        rows.append([
            sample_name,
            "TE",
            "1",
            dest_container,
            dest_well,
            "DNA 1",
            "x",
            str(norm_conc),
            str(sample_volume),
            str(buffer_volume)
            ])

    lims.put_batch(updated_outputs)

    output_file_name = output_file_id + "_norm.csv"
    with open(output_file_name, 'wb') as out_file:
        out = csv.writer(out_file)
        out.writerow(header)
        out.writerows(rows)

    if warning:
        print "Warning: too low input concentration for samples:", ", ".join(warning), "."
        sys.exit(1)

# Use:  PROCESS_ID OUTPUT_FILE_ID CONCENTRATION_SOURCE={"quantit"|"sample"}
main(sys.argv[1], sys.argv[2], sys.argv[3])

