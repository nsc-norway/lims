import sys
import re
import StringIO
import xlwt
from genologics.lims import *
from genologics import config

# Excel (xls) file generator for Hamilton robots for normalisation steps
# This is for the first steps in Nextera protocol

def sort_key(elem):
    input, output, sample = elem
    container, well = output.location
    row, col = well.split(":")
    return (container, int(col), row)


def main(process_id, filegen, file_id, params):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    if filegen in ["HamiltonDilution1", "HamiltonDilution2"]:
        norm_conc, vol = float(params[0]), float(params[1])

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
    if filegen in ["HamiltonDilution1", "Inputfil_Hamilton_Normalisering"]:
        samples = [input.samples[0] for input in inputs]
        lims.get_batch(samples)
        try:
            concentrations = [sample.udf['Sample conc. (ng/ul)'] for sample in samples]
        except KeyError:
            print "Missing value for 'Sample conc. (ng/ul)'."
            sys.exit(1)
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

    if filegen in ["HamiltonDilution1", "HamiltonDilution2", "Inputfil_Hamilton_Normalisering"]:
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
            if input.name.lower().startswith("blankprove-"):
                # Request from Silje: always use these parameters for BlankProve
                # Care: This even ignores the sepecified total volume
                sample_volume = 12
                buffer_volume = 13
            else:
                if input_conc > 0:
                    sample_volume = (norm_conc * vol * 1.0 / input_conc)
                else:
                    sample_volume = vol + 1
                buffer_volume = vol - sample_volume
                if buffer_volume < 0:
                    buffer_volume = 0.0
                    sample_volume = vol
                    warning.append(output.name)

            columns = [
                    ("Sample_Number", sample_no.group(1) if sample_no else sample_name),
                    ("Labware", "Rack%d" % ((index // 32) + 1)),
                    ("Position_ID", str((index % 32) + 1)),
                    ("Volume_DNA", sample_volume),
                    ("Volume_EB", buffer_volume),
                    ("Destination_Well_ID", well),
                ]
            # Updates information on each output sample
            output.udf['Normalized conc. (ng/uL)'] = norm_conc
            output.udf['Volume (uL)'] = vol

        elif filegen == "HamiltonDilution2":
            if input_conc > 0:
                sample_volume = (norm_conc * vol * 1.0 / input_conc)
            else:
                sample_volume = vol+1
            buffer_volume = vol - sample_volume 

            if buffer_volume < 0:
                buffer_volume = 0.0
                sample_volume = vol
                if not input.name.lower().startswith("blankprove-"):
                    warning.append(output.name)
            columns = [
                    ("Sample_Number", sample_no.group(1) if sample_no else sample_name),
                    ("Source_Well_ID", input.location[1].replace(":", "")),
                    ("Volume_DNA", round(sample_volume, 1)),
                    ("Destination_Well_ID", well),
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

# COMMAND LINE PARAMETERS
#-----------------------------
# For NEXTERA HAMILTON
#   Use:  main PROCESS_ID TYPE FILEID PARAMS_CONCENTRATION_AND_VOLUME
#   (params = [CONCENTRATION, VOLUME])
#   TYPE (filegen) is "HamiltonDilution1" or "HamiltonDilution2"

main(process_id=sys.argv[1], filegen=sys.argv[2], file_id=sys.argv[3], params=sys.argv[4:])
