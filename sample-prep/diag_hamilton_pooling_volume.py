import sys
import re
import xlwt
from genologics.lims import *
from genologics import config

# Script to generate XLS file for Hamilton pooling volumes

def main(process_id, file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    ios = [
            (i['uri'], o['uri'])
            for i, o in process.input_output_maps
            if o['output-type'] == 'Sample'
            ]

    lims.get_batch([i for i, o in ios] + [o for i,o in ios])

    book = xlwt.Workbook()
    sheet1 = book.add_sheet('Sheet1')

    row = sheet1.row(0)
    headers = ["SourceWell", "ng/uL", "PoolWell", "Index1", "Index2"]
    for i, header in enumerate(headers):
        row.write(i, header)

    ios_sorted = list(sorted(ios, key=row_order))
    concentrations = get_qc_concs(lims, [i for i, o in ios_sorted])

    io_conc = list(zip(ios_sorted, concentrations))
    min_conc_nonblank = min(c for (i,o), c in io_conc if not i.name.lower().startswith("blankprove-"))

    for i, ((input, output), conc) in enumerate(io_conc, 1):
        row = sheet1.row(i)
        row.write(0, input.location[1].replace(":", ""))
        if input.name.lower().startswith("blankprove-"):
            row.write(1, min_conc_nonblank)
        else:
            row.write(1, conc)
        row.write(2, output.location[1].replace(":", ""))
        i7, i5 = get_index_names(input)
        row.write(3, i7)
        row.write(4, i5)

    book.save(file_id + "-HamiltonNormPoolOutput.xls")

def get_index_names(output):
    try:
        index_name = output.reagent_labels[0]
    except:
        print("Missing index information for", output.name, ", aborting.")
        sys.exit(1)
    try:
        match = re.match(r"\d\d (N7\d\d)-(E5\d\d) .*", index_name)
        return match.group(1), match.group(2)
    except:
        print("Invalid index information for", output.name, " (unable to parse '" + index_name + "').")
        sys.exit(1)

def row_order(item):
    input, output = item
    return [input.location[0].id] + list(reversed(input.location[1].split(":")))

def get_qc_concs(lims, inputs):
    """Get concentration from any Quant-iT step
    
    Function copied from hamilton.py"""
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
            missing.append(input.name)
        else:
            concentrations.append(qi_conc)

    if missing:
        print("Missing QC results for", ",".join(missing), ".")
        sys.exit(1)
    return concentrations

# Use:  main PROCESS_ID FILE_ID
main(sys.argv[1], sys.argv[2])

