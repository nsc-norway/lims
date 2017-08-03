# -----------------------------------
# NSC Sample Sheet Generation Tool
# -----------------------------------
# This may be used instead of the sample sheet generator that
# is bundled with Clarity LIMS. It produces sample sheets in a
# format readable by bcl2fastq.

# This tools is only designed to create sample sheets for 
# bcl2fastq2, for the NSC-specific file and directory names.
# It needs access to the run-ID to generate these names, so it 
# can't be run before the sequencing run is started.

# ** Project file structure (NSC) **

# DIRECTORY NAME (HiSeq 2500/4000/X):
# <RunIdText>.Project_<ProjectName>/Sample_<SampleName>

# DIRECTORY NAME (Mi/NextSeq):
# <RunIdText>.Project_<ProjectName>/

# FILE NAME (HiSeq 2500):
# <SampleName>_<SampleIndexSequence>_L00<LaneNumber>_R<ReadNumber>_001.fastq.gz
# ex. TEST_GACTAGTA_L002_R2_001.fastq.gz

# FILE NAME (All except HiSeq 2500):
# <SampleName>_S<SampleSheetOrdinal>_R<ReadNumber>_001.fastq.gz
# ex. 7-IPF1-2k_S7_R1_001.fastq.gz


# The sample sheet contains sections delimited by keywords in 
# square brackets, e.g. [Data]. Because it is a CSV file, it 
# MAY have an equal number of commas on all lines, so the section
# header would be "[Data],,,,,," (This happens if it is edited in
# Excel, and then it remains a valid sample sheet).

# *** Format overview ***
# There are four sections: Header, Reads, Settings and Data
# The number of columns in each section is different. Data has the
# actual sample information, while the other sections are more 
# about defining the run parameters, etc. Thus, Data is the one
# primarily used by bcl2fastq. Further detail is probably best to
# glean from examples and from the code itself.

# The sample sheet is constructed as a list of lists, the elements
# of which represent rows and cells respectively.

import sys
import re
from genologics.lims import *
from genologics import config

def header_section():
    data = ['']

def reads_section(reads_cycles):
    return [[str(cycles)] for cycles in read_cycles]

def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)


    i_os = [(i['uri'], o['uri']) 
                for i, o in process.input_output_maps
                if o['output-generation-type'] == 'PerInput'
            ]

    lims.get_batch([i for i, o in i_os] + [o for i, o in i_os])
    if len(set(o.location[0] for i, o in i_os)) > 1:
        print "Only one output container (flowcell) may be used at a time"
        sys.exit(1)

    data = generate_sample_sheet(i_os, [], "TEST", True)


def generate_sample_sheet(i_os, reads_cycles, run_id, instrument):

    # Sort by output well (lane)
    sorted_i_os = sorted(i_os, key=lambda i,o: o.location[1])

    sample_index_lists = [get_samples_and_indexes(i) for i, o in sorted_i_os]
    lims.get_batch(sample
                for sample_index_list in sample_index_lists
                for sample, index in sample_index_list
                )
    

    # Actual sample sheet generation starts here
    data = [["[Header]"]] + header_section() +\
            [["[Reads]"]] + reads_section([]) +\
            [["[Data]"]]

    if instrument in ['miseq', 'nextseq']:
        col_headers = []
    else:
        col_headers = ['Lane']

    col_headers += [
            "Sample_ID",
            "Sample_Name",
            "Index",
        ]
    # Is it a single / dual / no index run?
    # Only if it's a dual indexed run should there be a index2 column
    indexes = [
            index 
            for sample_index_list in sample_index_lists
            for sample, index in sample_index_list
            ]
    if any('-' in index for index in indexes if index):
        col_headers.append("Index2")

    col_headers.append("Sample_Project")

    # Each i/o pair is a lane. Loop over lanes and add all samples in each
    for i, o, sample_index_list in zip(sorted_i_os, sample_index_lists):
        for sample, index in sample_index_list:
            data.append(get_sample_row(instrument, run_id, sample, index, col_headers))

    data.append([])
    return data


def get_samples_and_indexes(artifact):
    """Search down the ancestry of an artifact (pool) until a list of
    artifacts with a single index (or none) are found, and return the sample 
    objects and the indexes.
    
    At this point we rely on the LIMS to enforce that if there are multiple
    pooled samples, they must have unique (non-null) indexes."""
    if not artifact.reagent_labels:
        return [(artifact.samples[0], None)]
    if len(artifact.reagent_labels) == 1:
        return [(artifact.samples[0], next(iter(artifact.reagent_labels)))]
    else:
        parent = artifact.parent_process
        lims.get_batch(parent.all_inputs(unique=True))
        inputs = [i['uri']
                for i, o in parent.input_output_maps
                if o['output-generation-type'] == TODO_FILTER
                    and o['uri'].id == artifact.id
                    ]
        return sum(get_samples_and_indexes(i) for i in inputs, [])


def get_sample_row(instrument, run_id, sample, index, col_headers):
    cells = []
    if index is None:
        index1, index2 = "", ""
    else:
        parts = index.split("-")
        index1 = parts[0]
        if len(parts) > 1:
            if instrument in ['hiseq', 'miseq']:
                index2 = parts[1]
            else:
                index2 = reverse_complement(parts[1])
        else:
            index2 = ""

    for col_header in col_headers:
        if col_header == "Sample_ID":
            cells.append(sample.name)
        elif col_header == "Sample_Name":
            cells.append(sample.name)
        elif col_header == "Index":
            cells.append(index1)
        elif col_header == "Index2":
            cells.append(index2)
        elif col_header == "Sample_Project":
            cells.append(get_project_string(instrument, run_id, sample.project.name))

def get_project_string(instrument, run_id, project_name):
    pass


def reverse_complement(sequence):
    complement = {'A':'T', 'C':'G', 'G':'C', 'T':'A'}
    return reversed(complement.get(x, x) for x in sequence)


if __name__ == "__main__":
    # See main() signature for command line args
    main(*sys.argv[1:3])


