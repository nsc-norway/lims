import sys
import re
import StringIO
import xlwt
from genologics.lims import *
from genologics import config

# Excel (xls) file generator for Hamilton robots for normalisation steps

def sort_key(elem):
    input, output, sample = elem
    container, well = output.location
    row, col = well.split(":")
    return (container, int(col), row)


def main(process_id, filegen, file_id, norm_conc, vol):
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
    if filegen == "HamiltonDilution1":
        samples = [input.samples[0] for input in inputs]
        lims.get_batch(samples)
        concentrations = [sample.udf.get('Sample conc. (ng/ul)') for sample in samples]
    elif filegen == "HamiltonDilution2":
        # Look for sibling processes with QC information. Note that this only works
        # because we know that the artifacts are generated directly above in the workflow,
        # and go through a single Quant-iT step. If inputs were e.g. the root analyte, then
        # this procedure could give unexpected results.
        processes = sorted(
                lims.get_processes(inputartifactlimsid=[input.id for input in inputs]),
                key=lambda proc: proc.id
                )
        concentrations = []
        missing = []
        for input in inputs:
            qi_conc = None
            for qc_process in processes:
                if qc_process.type_name.startswith("Quant-iT"):
                    for i, o in qc_process.input_output_maps:
                        if i['uri'].id == input.id and o['output-type'] == "ResultFile"\
                                and o['output-generation-type'] == "PerInput":
                            conc = o['uri'].udf.get('Concentration')
                            if conc is not None:
                                qi_conc = conc
            if qi_conc is None:
                missing.append(i['uri'].name)
            else:
                concentrations.append(qi_conc)

        if missing:
            print "Missing QC results for", ",".join(missing), "."
            sys.exit(1)
    else:
        concentrations = [None]*len(inputs)

    if filegen in ["HamiltonDilution1", "HamiltonDilution2"]:
        missing_udf = [input.name for input, conc in zip(inputs, concentrations) if conc is None]
        if missing_udf:
            print "Error: input concentration not known for samples", ", ".join(missing_udf)
            sys.exit(1)
    
    warning = []
    missing_udf = []
    headers = []
    i_o_s = zip(inputs, outputs, concentrations)
    for index, (input, output, input_conc) in enumerate(sorted(i_o_s, key=sort_key)):
        sample_name = input.name.encode('utf-8')

        well = output.location[1].replace(":","")

        sample_no = re.match(r"([0-9]+)-", sample_name)
        if filegen == "HamiltonDilution1":
            # (20 ng/uL * 25 uL) / conc = (500 ng) / conc
            sample_volume = (norm_conc * vol * 1.0 / input_conc)
            buffer_volume = vol - sample_volume

            if buffer_volume < 0:
                buffer_volume = 0.0
                sample_volume = vol
                warning.append(output.name)
            columns = [
                    ("Sample_Number", sample_no.group(1) if sample_no else sample_name),
                    ("Labware", "Rack%d" % (i//32 + 1)),
                    ("Position_ID", str(index+1)),
                    ("Volume_DNA", sample_volume),
                    ("Volume_EB", buffer_volume),
                    ("Destination_Well_ID", well),
                ]
            # Updates information on each output sample
            output.udf['Normalized conc. (ng/uL)'] = norm_conc
            output.udf['Volume (uL)'] = vol

        elif filegen == "HamiltonDilution2":
            sample_volume = (norm_conc * vol * 1.0 / input_conc)
            buffer_volume = vol - sample_volume 

            if buffer_volume < 0:
                buffer_volume = 0.0
                sample_volume = vol
                warning.append(output.name)
            columns = [
                    ("Sample_Number", sample_no.group(1) if sample_no else sample_name),
                    ("Well_ID", well),
                    ("Volume_DNA", sample_volume),
                ]

            output.udf['Normalized conc. (ng/uL)'] = norm_conc
            output.udf['Volume (uL)'] = vol


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
    filename = filegen + ".xls"
    gs = lims.glsstorage(outfile, filename)
    file_obj = gs.post()
    file_obj.upload(outputstream.getvalue())

    if warning:
        print "Warning: too low input concentration for samples:", ", ".join(warning), "."
        sys.exit(1)

# Use:  main PROCESS_ID TYPE FILEID CONCENTRATION VOLUME
main(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]))

