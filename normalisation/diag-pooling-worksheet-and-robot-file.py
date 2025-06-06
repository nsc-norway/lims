import sys
import csv
import re
import xlwt
from genologics.lims import *
from genologics import config

# Pooling script for the following scenario:
#  * Equimolar pooling of WGS libraries ("normal" samples)
#  * Optional addition (spike-in) of pool of targeted libraries into WGS pool ("special" samples)

# The spike-in pool is referred to a "special" pool/sample below. The calculations are
# based on requirements specified by the lab, and are somewhat complex. The spike-in
# should not be counted in the final concentration. The relative spike-in amount should
# be adjusted based on the final input concentration used for the sequencer, so the spike-in
# pool is always loaded at the same input concentration - step UDF "EKG pool target molarity (nM)".


TUBE = 'Tube'

def get_tuple_key(input_artifact):
    container = input_artifact.location[0].name
    well = input_artifact.location[1]
    row, col = well.split(":")
    return (container, int(col), row)


def is_special_ekg_pool(artifact):
    """Find samples that have been created in the EKG pooling step.
    
    These samples should be processed in a completely different way than normal equimolar
    pooling samples. They should be spiked into the pool with lower molarity, and they
    are not part of the target molarity calculation for normal samples."""

    has_run_through_ekg_pooling = artifact.parent_process and \
        (artifact.parent_process.type_name.startswith("Pooling and normalization EKG Diag ") or \
        artifact.parent_process.type_name=="Pooling and normalization Diag 4.4")
    has_ekg_project_name = artifact.samples[0].project.name.startswith("Diag-EKG")
    return has_run_through_ekg_pooling or has_ekg_project_name


def get_sample_details(pool_input_samples, pool_pool_volume, target_sample_conc, input_tubes,
                        target_special_pool_molarity):

    """
    pool_input_samples:   List of Artifacts to be pooled
    pool_pool_volume:     Desired pool volume of the pool to create
    target_sample_conc:   The target molarity of the pool (normal samples only)
    input_tubes:          List of input tubes used for special pools - used to count sequential well numbers
    target_special_pool_molarity: Desired molarity of the special pool, after correcting for loading concentration
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

        # Determine pooling volumes.
        # There are two cases: normal equimolar pooling and special
        # spiking of EKG (cancer panel) pools into pools of normal WGS samples. The rules for such
        # spike-in is that their molarity should not count towards the total molarity of the pool - 
        # in the sense that the final pool molarity will exceed the specified target molarity.
        special_type = is_special_ekg_pool(input)
        if special_type:
            # Compute volume for special library (sub-pool) using standard formula
            target_molarity = target_special_pool_molarity 
            sample_volume = pool_pool_volume * target_molarity / sample_molarity
            all_special_samples = input.lims.get_batch(input.samples)
            all_special_projects = set(sam.project for sam in all_special_samples)
            sample_name = "|".join(project.name for project in all_special_projects if project)

            # Keep track of input tubes for special_type input units, so the "source well" can be
            # a number corresponding to the ordinal of the tube.
            if input.location[0].id in input_tubes:
                print("ERROR: Input tube {} is used twice".format(input.location[0].name))
                sys.exit(1)
            input_tubes.append(input.location[0].id)
            source_well = len(input_tubes)
        else:
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
            'special_type': special_type,
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

    # The order of input tubes (for special pools only) is chosen as the same order as the
    # tubes appear in the output file.
    input_tubes = []
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
        # Note: In case of special samples, the actual targets will deviate from the specified molarity,
        # as the special samples are added on top.
        output = pool.output
        try:
            pool_norm_conc = output.udf['Normalized conc. (nM)']
            pool_pool_volume = output.udf['Volume (uL)']
        except KeyError as e:
            print("Missing field {} on pool {}.".format(e, pool.name))
            sys.exit(1)

        # Determine concentration for normal samples / pools. We're not supposed to count the
        # special samples for this calculation.
        num_normal_samples = max(
            sum(1 for x in pool.inputs if not is_special_ekg_pool(x)),
            1 # Prevent zero division if there's only a CuCa pool
        )
        target_sample_conc = pool_norm_conc * 1.0 / num_normal_samples

        # The UDF 'EKG pool target molarity (nM)' refers to the final input
        # concentration on the NovaSeq, after potentially another dilution in the Dilute and 
        # Denature step. We compute the molarity that the component pool has to have now.
        base_special_molarity = process.udf.get('EKG inputkons. (nM)')
        if base_special_molarity is None:
            adjusted_special_molarity = None
        else:
            nov_input_conc = output.udf['Input Conc. (nM)']
            adjusted_special_molarity = base_special_molarity * pool_norm_conc / nov_input_conc

        # Get a list of sample information dicts
        samples, error2 = \
            get_sample_details(pool.inputs, pool_pool_volume, target_sample_conc, input_tubes,
                                target_special_pool_molarity=adjusted_special_molarity)

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

    special_sample_report = []
    for pool in pool_list:
         for sample in pool:
             if sample["special_type"]:
                 special_sample_report.append("{:10} {:10} {:7.4f} nM".format(sample['pool_name'], sample['sample_name'], sample['target_molarity']))
    if special_sample_report:
        process.udf['EKG Normalization concs. (nM)'] = "\n".join(special_sample_report)
        process.put()

    write_worklist_file(pool_list, worksheet_file_name)
    write_robot_file(pool_list, robot_file_name)

    sys.exit(1 if error else 0)


main(*sys.argv[1:4])

