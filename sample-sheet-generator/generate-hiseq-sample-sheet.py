# -----------------------------------
# NSC Sample Sheet Generation Tool 2
# -----------------------------------

# This aims to replace the GLS sample sheet generator, with only two
# modifications:
# - Better performance
# - Select sample ID values


import sys
import re
import datetime
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

reagent_type_uri = {}
reagent_type_seq = {}

def get_all_reagent_types():
    """Load all reagent types with name only, from the API resource.
    (this is a lot faster than getting the full representations one by
    one)."""
    # Using a loop similar to Lims._get_instances()
    reagent_types = {}
    root = lims.get(lims.get_uri("reagenttypes"))
    while root:
        for node in root.findall("reagent-type"):
            # add a reagent type to the dict by name
            name = node.attrib['name']
            uri = node.attrib['uri']
            reagent_types[name] = uri
        node = root.find('next-page')
        root = None
        if not node is None:
            root = lims.get(node.attrib['uri'])
    return reagent_types


def main(use_sampleid, process_id, output_file_id):
    global reagent_type_uri

    process = Process(lims, id=process_id)
    i_os = [(i['uri'], o['uri']) 
                for i, o in process.input_output_maps
                if o['output-generation-type'] == 'PerInput'
            ]

    lims.get_batch([i for i, o in i_os] + [o for i, o in i_os])
    if len(set(o.location[0] for i, o in i_os)) > 1:
        print("Only one output container (flowcell) may be used at a time")
        sys.exit(1)

    reagent_type_uri = get_all_reagent_types()

    data = generate_sample_sheet(process, i_os, use_sampleid == "-i")

    # Upload sample sheet with name of flow cell ID
    csv_data = "\r\n".join(",".join(cel for cel in row) for row in data)
    outfile = Artifact(lims, id=output_file_id)
    filename = i_os[0][1].location[0].name + ".csv" # Name after FCID
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
                ]
    except KeyError as e:
        print("Missing information:", e)
        sys.exit(1)


def reads_section(reads_cycles):
    return [[str(cycles)] for cycles in reads_cycles]


def get_sample_index(index, reverse_complement_index2, max_length, dropi1, dropi2):
    if index is None:
        return "", ""
    else:
        parts = index.split("-")
        index1 = parts[0]
        if len(parts) > 1:
            if reverse_complement_index2:
                index2 = reverse_complement(parts[1])
            else:
                index2 = parts[1]
        else:
            index2 = ""
        if max_length:
            index1 = index1[:max_length]
            index2 = index2[:max_length]
        if dropi1: index1 = ""
        if dropi2: index2 = ""
        return index1, index2


def generate_sample_sheet(process, i_os, use_sampleid=False):

    # Sort by output well (lane)
    sorted_i_os = sorted(i_os, key=lambda i_o: (i_o[1].location[1], i_o[0].name))

    sample_index_lists = [get_samples_and_indexes(i) for i, o in sorted_i_os]
    lims.get_batch(sample
                for sample_index_list in sample_index_lists
                for sample, artifact, index in sample_index_list
                )

    reads_cycles = get_reads_cycles(process)

    # Actual sample sheet generation starts here
    data = [["[Header]"]] + header_section(process) +\
            [["[Reads]"]] + reads_section(reads_cycles) +\
            [["[Data]"]]

    data.append([
            "Lane",
            "Sample_ID",
            "Sample_Name",
            "Index",
            "Index2",
            "Sample_Project",
            "Description"
        ])

    # Use reverse complement only for PE runs
    reverse_complement_index2 = len(reads_cycles) == 2
    cgwf = process.udf.get('Cluster Generation Workflow')
    if cgwf:
        if cgwf.startswith("Paired") != reverse_complement_index2:
            print("Error: inconsistent values for Cluster Generation Workflow ({}), and "
                    "number of cycles in [Read1, Read2]: {}.".format(
                        process.udf['Cluster Generation Workflow'],
                        reads_cycles
                        ))
            sys.exit(1)

    if process.udf.get('Truncate index sequence'):
        max_length = 8 # process.get('Index 1 Read Cycles', 0)
    else:
        max_length = None

    validate = process.udf.get('Validate indexes')
    dropi1 = process.udf.get('Drop index1 in sample sheet')
    dropi2 = process.udf.get('Drop index2 in sample sheet')

    # Each i/o pair is a lane. Loop over lanes and add all samples in each
    for (i, o), sample_index_list in zip(sorted_i_os, sample_index_lists):
        used_indexes = []
        well, well_, well_ = o.location[1].partition(':')
        for sample, artifact, index in sample_index_list:
            index1, index2 = get_sample_index(index, reverse_complement_index2, max_length, dropi1, dropi2)
            used_indexes.append((index1, index2))
            if use_sampleid:
                data.append([
                            well,
                            artifact.id,
                            sample.name,
                            index1,
                            index2,
                            sample.project.name,
                            ""
                        ])
            else:
                data.append([
                            well,
                            sample.name,
                            sample.name,
                            index1,
                            index2,
                            sample.project.name,
                            artifact.id
                        ])
        if validate:
            if len(set(len(index1)+len(index2) for index1,index2 in used_indexes)) > 1:
                print("Validation error in lane {}: different index lengths".format(well))
                sys.exit(1)
            if len(set(used_indexes)) < len(used_indexes):
                non_unique = list(used_indexes)
                for index in set(used_indexes):
                    non_unique.remove(index)
                print("Indexes not unique in lane {}: {}. To ignore this, turn off Validate indexes.".format(
                    well, ", ".join("-".join(i for i in (i1, i2) if i) for i1,i2 in non_unique))
                    )
                sys.exit(1)

    data.append([])
    return data


def get_samples_and_indexes(artifact):
    """Search down the ancestry of an artifact (pool) until a list of
    artifacts with a single index (or none) are found, and return the sample 
    objects and the indexes.
    
    At this point we rely on the LIMS to enforce that if there are multiple
    pooled samples, they must have unique (non-null) indexes."""
    if not artifact.reagent_labels:
        return [(artifact.samples[0], artifact, None)]
    if len(artifact.reagent_labels) == 1:
        index_name = next(iter(artifact.reagent_labels))
        try:
            index_seq = reagent_type_seq[index_name]
        except KeyError:
            try:
                reagent_obj = ReagentType(lims, uri=reagent_type_uri[index_name])
                index_seq = reagent_obj.sequence
                reagent_type_seq[index_name] = index_seq
            except KeyError as e:
                print("Index reagent name {0} is not available in the system.".format(e))
                sys.exit(1)
        return [(artifact.samples[0], artifact, index_seq)]
    else:
        parent = artifact.parent_process
        lims.get_batch(parent.all_inputs(unique=True))
        inputs = [i['uri']
                for i, o in parent.input_output_maps
                    if o['uri'].id == artifact.id ]
        return sum((get_samples_and_indexes(i) for i in inputs), [])


def reverse_complement(sequence):
    complement = {'A':'T', 'C':'G', 'G':'C', 'T':'A'}
    return "".join(reversed([complement.get(x, x) for x in sequence]))


def hamming_distance(s1, s2):
    return sum(c1 != c2 for c1, c2 in zip(s1,s2))


if __name__ == "__main__":
    # Arguments: {-i|-n} PROCESSID OUTPUT_LIMSID
    # Option -i: Use LIMSID as SampleID
    #        -n: Use sample name as SampleID
    main(*sys.argv[1:])


