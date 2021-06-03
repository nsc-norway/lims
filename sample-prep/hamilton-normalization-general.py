import sys
import re
import StringIO
import xlwt
from genologics.lims import *
from genologics import config

# Excel (xls) file generator for Hamilton robots for normalisation steps
# For TruSeq PCR-free (WGS) and SureSelect Exome prep.

# { Concentration => volume } mapping for SureSelect
DEFAULT_OUTPUT_VOL = {
        3000: 130,
        200: 50
        }

def sort_key(elem):
    output = elem[1]
    container, well = output.location
    row, col = well.split(":")
    return (container, int(col), row)


def main(process_id, concentration_source, file_id, default_vol):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    book = xlwt.Workbook()
    sheet1 = book.add_sheet('Sheet1')

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

    if concentration_source == "sample":
        concentrations = [sample.udf.get('Sample conc. (ng/ul)') for sample in samples]
    else:
        concentrations = [input.udf.get('Concentration (ng/ul)') for input in inputs]

    missing_udf = [input.name for input, conc in zip(inputs, concentrations) if conc is None]
    if missing_udf:
        print "Error: input concentration not known for sample(s)", ", ".join(missing_udf)
        sys.exit(1)
    
    warning = []
    headers = []
    i_o_s = zip(inputs, outputs, samples, concentrations)
    tube_counter = 0
    for index, (input, output, sample, input_conc) in enumerate(sorted(i_o_s, key=sort_key)):
        
        sample_name = input.name.encode('utf-8')
        sample_no = re.match(r"([0-9]+)-", sample_name)
        well = output.location[1].replace(":","")
        try:
            norm_mass = output.udf['Amount of DNA per sample (ng)']
        except KeyError:
            print "Error: Missing value for Amount of DNA per sample (ng) on", output.name, "(and possibly others)"
            sys.exit(1)

        # Use output-level UDF, fallback to input-specific default, then global default
        vol = output.udf.get('Volume (uL) Diag', float(default_vol))
        output.udf['Volume (uL) Diag'] = vol
        
        if input_conc == 0.0:
            sample_volume = vol + 1 # Will produce a warning below
        else:
            sample_volume = norm_mass * 1.0 / input_conc

        buffer_volume = vol - sample_volume

        if buffer_volume < 0:
            buffer_volume = 0.0
            sample_volume = vol
            warning.append(output.name)

        # Different handling of tube and 96 plate
        if input.location[0].type_name == '96 well plate':
            labware = "Rack2DTubes"
            position_id = input.location[1].replace(":", "")
        else:
            labware = "Rack%d" % ((tube_counter // 32) + 1)
            position_id = str((tube_counter % 32) + 1)
            tube_counter += 1

        columns = [
                ("Sample_Number", sample_no.group(1) if sample_no else sample_name),
                ("Archive pos.", sample.udf.get('Archive position Diag', '')),
                ("Alt sample ID", sample.udf.get('Alternative sample ID Diag', '')),
                ("Sample conc.", round(input_conc, 2)),
                ("Labware", labware),
                ("Position_ID", position_id),
                ("Volume_DNA", round(sample_volume, 1)),
                ("Volume_EB", round(buffer_volume, 1)),
                ("Destination_Well_ID", well),
                ("Norm. conc.", round(norm_mass * 1.0 / vol, 2)),
            ]

        if not headers:
            row = sheet1.row(0)
            headers = [x[0] for x in columns]
            for i, header in enumerate(headers):
                row.write(i, header, xlwt.easyxf('pattern: pattern solid, fore_color yellow;'))

        row = sheet1.row(index+1)
        for i, val in enumerate([x[1] for x in columns]):
            row.write(i, val)

    lims.put_batch(outputs)

    outputstream = StringIO.StringIO()
    book.save(outputstream)

    outfile = Artifact(lims, id=file_id)
    filename = "Inputfil_Hamilton_Normalisering.xls"
    gs = lims.glsstorage(outfile, filename)
    file_obj = gs.post()
    file_obj.upload(outputstream.getvalue())

    if warning:
        print "Warning: too low input concentration for samples:", ", ".join(warning), "."
        sys.exit(1)


main(process_id=sys.argv[1], concentration_source=sys.argv[2], file_id=sys.argv[3],
                default_vol=sys.argv[4])
