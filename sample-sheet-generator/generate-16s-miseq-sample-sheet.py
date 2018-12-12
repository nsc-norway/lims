# -----------------------------------
# NSC Sample Sheet Generation Tool
# -----------------------------------

# Special purpose sample sheet generator for internal barcodes.
# It ignores the sample information and adds a single dummy
# sample without index.


import sys
import re
import datetime
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

def main(process_id, output_file_id):
    process = Process(lims, id=process_id)
    assert len(process.all_inputs()) == 1, "Only one input expected."
    data = generate_sample_sheet(process, process.all_inputs()[0])

    # Upload sample sheet with name of reagent cartridge ID
    csv_data = "\r\n".join(",".join(cel for cel in row) for row in data)
    outfile = Artifact(lims, id=output_file_id)
    output_pool = next(io[1]['uri'] for io in process.input_output_maps
            if io[1]['output-generation-type'] == 'PerInput')
    filename = output_pool.location[0].name + ".csv" # Name after ID
    gs = lims.glsstorage(outfile, filename)
    file_obj = gs.post()
    file_obj.upload(csv_data.encode('ascii'))


def get_reads_cycles(process):
    try:
        reads_cycles = [int(process.udf['Read 1 Cycles'])]
    except:
        print("Invalid number of Read 1 Cycles:",
                process.udf.get('Read 1 Cycles', '<Blank>'))
        sys.exit(1)
    if 'Read 2 Cycles' in process.udf:
        r2cycles = int(process.udf['Read 2 Cycles'])
        if r2cycles > 0:
            reads_cycles.append(r2cycles)
    return reads_cycles


def filter_ascii(data):
    return "".join(c for c in data if ord(c) < 127)


def header_section(process):
    try:
        return [['Investigator Name', filter_ascii(process.technician.name)],
                ['Experiment Name', process.udf['Experiment Name']],
                ['Date', str(datetime.date.today())],
                ['Workflow', 'GenerateFASTQ'],
                ['Chemistry', ''],
                ]
    except KeyError as e:
        print("Missing information:", e)
        sys.exit(1)


def reads_section(reads_cycles):
    return [[str(cycles)] for cycles in reads_cycles]


def generate_sample_sheet(process, artifact):
    reads_cycles = get_reads_cycles(process)

    # Actual sample sheet generation starts here
    data = [["[Header]"]] + header_section(process) +\
            [["[Reads]"]] + reads_section(reads_cycles) +\
            [["[Data]"]]

    data.append([
            "Sample_ID",
            "Sample_Name",
            "Index",
            "Sample_Project"
        ])
    
    sample = next(iter(s for s in artifact.samples if not s.control_type))

    data.append([
        "Pool",
        "Pool",
        "",
        sample.project.name
        ])

    data.append([])
    return data


if __name__ == "__main__":
    # Arguments: PROCESSID OUTPUT_LIMSID
    main(*sys.argv[1:])


