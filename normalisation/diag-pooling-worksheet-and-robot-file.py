import sys
import csv
import re
import xlwt
from genologics.lims import *
from genologics import config

# Pooling script for the following scenario:
#  * Equimolar pooling of WGS libraries ("normal" samples)


TUBE = 'Tube'

def get_tuple_key(input_artifact):
    container = input_artifact.location[0].name
    well = input_artifact.location[1]
    row, col = well.split(":")
    return (container, int(col), row)


def get_sample_details(pool_input_samples, pool_pool_volume, target_sample_conc):

    """
    pool_input_samples:   List of Artifacts to be pooled
    pool_pool_volume:     Desired pool volume of the pool to create
    target_sample_conc:   The target molarity of the pool (normal samples only)
    """
    target_sample_conc_str = "%4.2f" % target_sample_conc

    unknown_molarity = []
    samples = []

    error = False

    for input in sorted(pool_input_samples, key=get_tuple_key):
        if 'Molarity' in input.udf:
            # Make it not zero or negative since we're dividing by it
            sample_molarity = max(input.udf['Molarity'], 0.0000001)
        else:
            unknown_molarity.append(input.name)
            continue # Error condition - but find all errors before aborting

        # Determine pooling volumes - equimolar pooling
        if not error and input.udf['Molarity'] < target_sample_conc:
            # Report soft error about too low concentration / too high volume
            print ("Warning: Molarity of", input.name, "is", input.udf['Molarity'],
                    ", which is less than the target per-sample molarity",
                    target_sample_conc, ".")
            error = True
            
        target_molarity = target_sample_conc 
        sample_volume = pool_pool_volume * target_sample_conc / sample_molarity
        sample_name = input.name
        # The location should be in a plate. If it's tubular instead, the source will be '11'
        # (because the location in the tube is 1:1).
        source_well = input.location[1].replace(":", "")
        
        samples.append({
            'sample_name': sample_name,
            'source_container_type': input.location[0].type_name,
            'source_container': input.location[0].name,
            'source_well': source_well,
            'sample_molarity': sample_molarity,
            'sample_volume': sample_volume,
            'target_molarity': target_molarity,
        })

    if unknown_molarity:
        print("ERROR: The Molarity field is missing for pool members ",
                ", ".join(unknown_molarity))
        sys.exit(1)

    return samples, error


def write_worklist_file(pools, output_filename):
    header = [
            "Pool",
            "Dest. cont.",
            "Well",
            "Pool molarity",
            "Pool volume",
            "Buffer volume",
            "Sample",
            "Source cont.",
            "Well",
            "Sample molarity",
            "Sample volume"
            ]
    rows = []
    for pool_samples in pools:
        first_in_pool = True
        for sample in pool_samples:

            if first_in_pool:
                row_first_part = [
                    sample['pool_name'],
                    sample['dest_container'],
                    sample['dest_well'],
                    "%4.2f" % sample['pool_norm_conc'],
                    "%4.2f" % sample['pool_pool_volume'],
                    "%4.2f" % sample['buffer_volume'],
                ]
                first_in_pool = False
            else:
                row_first_part = ["", "", "", "", "", ""]

            rows.append(row_first_part + [
                sample['sample_name'],
                sample['source_container'],
                sample['source_well'],
                "%4.2f" % sample['sample_molarity'],
                "%4.2f" % sample['sample_volume'],
                ])

    with open(output_filename, 'w', encoding='utf-8') as out_file:
        out = csv.writer(out_file)
        out.writerow(header)
        out.writerows(rows)


def write_robot_file(pools, output_filename):
    headers = [
            "SourceLabware",
            "Source Well",
            "Destination Well",
            "Sample Volume",
            "Pool Volume"
            ]

    book = xlwt.Workbook()
    sheet1 = book.add_sheet('Sheet1')
    row_index = 0
    row = sheet1.row(row_index)
    for i, header in enumerate(headers):
        row.write(i, header)

    for pool in pools:
        for sample in pool:
            row_index += 1
            row = sheet1.row(row_index)
            labware = "InputTubeRack" if sample['source_container_type'] == TUBE else "InputPlate"
            row.write(0, labware)
            row.write(1, sample['source_well'])
            row.write(2, sample['dest_well'])
            row.write(3, round(sample['sample_volume'], 1))
            row.write(4, round(sample['pool_pool_volume'], 1))

    book.save(output_filename)


def main(process_id, robot_file_name, worksheet_file_name):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    # Clear the output files, to make sure old data don't remain in case we have an accident
    for filename in [worksheet_file_name, robot_file_name]:
        with open(filename, 'w') as f:
            f.write("")

    step = Step(lims, id=process.id)

    # Precache the inputs and outputs
    lims.get_batch(process.all_inputs(unique=True) + process.all_outputs(unique=True))
    lims.get_batch(input.samples[0] for input in process.all_inputs(unique=True))

    output_tubes = sorted(set(
        int(oup.location[0].id.partition("-")[2]) for oup in process.all_outputs()
        if oup.type == 'Analyte' and oup.location[0].type_name == TUBE
    ))

    error = False # "Soft" error, still will upload the file

    rows = []
    pool_list = []
    # Relying on the API to return the pools in the same order as the user wants.
    for pool in step.pools.pooled_inputs:

        # Configured target output conc and volumes
        output = pool.output
        try:
            pool_norm_conc = output.udf['Normalized conc. (nM)']
            pool_pool_volume = output.udf['Volume (uL)']
        except KeyError as e:
            print("Missing field {} on pool {}.".format(e, pool.name))
            sys.exit(1)

        # Determine concentration for normal pools
        num_normal_samples = max(len(pool.inputs), 1)
        target_sample_conc = pool_norm_conc * 1.0 / num_normal_samples

        # Get a list of sample information dicts
        samples, error2 = get_sample_details(pool.inputs, pool_pool_volume, target_sample_conc)

        error = error or error2

        # Compute total sample volume, to determine amount of buffer
        total_sample_volume = sum(sample['sample_volume'] for sample in samples)
        buffer_volume = pool_pool_volume - total_sample_volume

        if not error and buffer_volume < 0:
            print("Total sample volume in pool", pool.name, "is", total_sample_volume,
                "uL, which exceeds the target pool volume", pool_pool_volume, ".")
            error = True

        dest_container = output.location[0].name
        if output.location[0].type_name == TUBE:
            dest_well = output_tubes.index(int(output.location[0].id.partition("-")[2])) + 1
        else:
            dest_well = output.location[1].replace(":", "")

        # Set pool-level information for all samples
        for sample in samples:
            sample['pool_name'] = pool.name
            sample['dest_well'] = dest_well
            sample['dest_container'] = dest_container
            sample['pool_norm_conc'] = pool_norm_conc
            sample['pool_pool_volume'] = pool_pool_volume
            sample['buffer_volume'] = buffer_volume

        pool_list.append(samples)

    # Now pool_list looks like this
    # pool_list = [
    #   [{'sample_name': 'sample1', 'sample_volume': 0.0, ....}, {pool1_sample2}, ...],
    #   [{pool2_sample1}, ...],
    #   ....   
    #]

    write_worklist_file(pool_list, worksheet_file_name)
    write_robot_file(pool_list, robot_file_name)

    sys.exit(1 if error else 0)


main(*sys.argv[1:4])

