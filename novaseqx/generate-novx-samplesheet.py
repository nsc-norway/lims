from genologics.lims import *
from genologics import config
import sys
import traceback
import os
import re
import operator
import logging
from collections import defaultdict
import pandas as pd
import jinja2
import lib.demultiplexing


def get_index_sequences(lims, reagent_label_list):
    """Convert reagent label names (strings) into tuples of (index1, index2) by looking up the sequences
    in LIMS. Empty strings are used if there is no index."""

    # This can be done the fast way or the right way. The names should all contain
    # the sequences in parenthesis as part of the reagent label names. We could extract
    # them, but instead we do it the slow way and fetch all the reagent label entities
    # and get their sequence attribute. First we do a search to convert the names into IDs
    # (or rather, ReagentType objects), then we fetch the entities one by one. The entities
    # will be cached between lanes, but the name search will be repeated.

    logging.info("Retrieving index sequences from LIMS API.")

    # First retrieve all reagent labels
    reagent_types = lims.get_reagent_types(name=[name for name in reagent_label_list if name])
    # This will fetch all reagent types from API
    reagent_type_map = {rt.name: rt for rt in reagent_types}

    result_index_list = []
    for reagent_label in reagent_label_list:
        if not reagent_label:
            result_index_list.append(('', ''))
        else:
            if reagent_label in reagent_type_map:
                seq_parts = reagent_type_map[reagent_label].sequence.split("-")
                if len(seq_parts) == 1: # Single index
                    result_index_list.append((seq_parts[0], ''))
                elif len(seq_parts) == 2: # Dual index
                    result_index_list.append(tuple(seq_parts))
                else:
                    raise ValueError(f"Reagent type {reagent_label} has malformed sequence in LIMS: {reagent_type_map[reagent_label].sequence}.")
            else:
                raise ValueError(f"Reagent type {reagent_label} referenced in artifact but does not exist.")

    return result_index_list



def hamming_distance(seq1, seq2):
    """Hamming distance between two strings of equal length.
    
    This is a helper method used in check_index_compatibility."""

    return sum(c1 != c2 for c1, c2 in zip(seq1, seq2))


def check_index_compatibility(index_pair_list, maximum_allowed_mismatches):
    """Check that indexes are sufficiently different from each other, so that reads can be uniquely
    attributed to a single sample, based on the configured allowed mismatches.
    """

    difference_threshold = 2 * maximum_allowed_mismatches
    found_any_failing = False
    # Compute all against all distances
    for i, (index1, index2) in enumerate(index_pair_list):
        for (index1_other, index2_other) in index_pair_list[i+1:]:
            index1_mismatches = hamming_distance(index1, index1_other)
            index2_mismatches = hamming_distance(index2, index2_other)

            # The samples can be distinguished if the mismatch count in either index is 
            # greater than the allowed mismatches plus one.
            index1_ok = index1_mismatches > difference_threshold
            index2_ok = index2_mismatches > difference_threshold
            if (not index1_ok) and (not index2_ok):
                index_display = "-".join([i for i in [index1, index2] if i])
                index_other_display = "-".join([i for i in [index1, index2] if i])
                logging.warning(f"Index {index_display} is too similar to {index_other_display}. "
                                f"Index1 mismatches: {index1_mismatches}, index2 mismatches: {index2_mismatches}.")
                logging.warning(f"With {maximum_allowed_mismatches} allowed mismatches, the difference shoud be "
                                f"greater than {difference_threshold} differences.")
                found_any_failing = True
            
    return not found_any_failing


def upload_samplesheet(lims, output_samplesheet_artifact, file_name, samplesheet_data):
    """Upload the sample sheet to the specified artifact."""

    gs = lims.glsstorage(output_samplesheet_artifact, file_name)
    file_obj = gs.post()
    file_obj.upload(samplesheet_data)


def clear_samplesheet(output_samplesheet_artifact):
    """Remove the file from the specified placeholder artifact. In case of errors we should clear the samplesheet."""

    if output_samplesheet_artifact.files:
        output_samplesheet_artifact.files[0].delete()


def get_override_cycles(r1c, r2c, i1c, i2c, sample_i1, sample_i2):
    """Get the override cycles for the sample, if the sample has a different index length than the process."""

    override_string = f"Y{r1c}"
    if i1c > 0:
        # Sequencer is running an index read 1
        override_string += f";"
        if sample_i1 > 0:
            override_string += f"I{sample_i1}"
        skip_cycles = i1c - sample_i1
        if skip_cycles > 0:
            override_string += f"N{skip_cycles}"
    if i2c > 0:
        # Sequencer is running an index read 2
        # In index2, skipping should come before the index read
        override_string += ";"
        skip_cycles = i2c - sample_i2
        if skip_cycles > 0:
            override_string += f"N{skip_cycles}"
        if sample_i2 > 0:
            override_string += f"I{sample_i2}"
    if r2c != 0:
        # Running read 2
        override_string += f";Y{r2c}"
    return override_string


def generate_saample_sheet(process_id, output_samplesheet_luid):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    step = Step(lims, id=process_id)
    warning_flag = False
    logging.info(f"Generating NovaSeq X SampleSheet file for process {process.id} and will upload to artifact ID {output_samplesheet_luid}")

    # Get the output Analyte artifact, corresponding to lanes of the flow cell
    output_artifacts = process.all_outputs(unique=True, resolve=True)
    output_lanes = [o for o in output_artifacts if o.type == 'Analyte']

    # Get and pre-cache all the samples, to determine analysis types etc.
    samples = lims.get_batch([s for a in output_lanes for s in a.samples])

    # Check flow cell type compatibility
    flowcell_type = process.udf['Flow Cell Type']
    container = next(iter(output_lanes)).location[0] # Placement script assures that there is just one container
    container_size = container.type.y_dimension['size']
    if flowcell_type in ['10B', '25B']:
        if container_size != 8:
            raise ValueError(f"The 8-tube strip should be used for a 10B or 25B flow cell, but found container size {container_size}.")
    elif flowcell_type == '1.5B':
        if container_size != 2:
            raise ValueError(f"The 2-tube strip should be used for a 1.5B flow cell, but found container size {container_size}.")
    else:
        logging.warning(f"Unknown Flow Cell Type '{flowcell_type}'.")

    # Get the library tube strip ID
    library_tube_strip_id = container.name
    # This check is important to prevent writing unexpected files - see output file below
    assert all((c.isalnum() or c in ['-']) for c in library_tube_strip_id), "Illegal characters in library strip tube name"
    
    # Process each lane and produce BCLConvert and DragenGermline sample tables
    bclconvert_rows = []
    dragen_germline_rows = []

    analysis_settings = []
    has_any_non_diag_samples = False # Run-level flag to determine compression format
    for lane_artifact in sorted(output_lanes, key=lambda artifact: artifact.location[1][0]):
        # Get lane from well position e.g. B:1 is lane 2.
        lane_id = int(lane_artifact.location[1].split(":")[0])
        barcode_mismatches = lane_artifact.udf['BarcodeMismatches']

        logging.info(f"Processing lane {lane_id}, artifact {lane_artifact.name}. Barcode mismatches = {barcode_mismatches}.")
        
        # Get the demux endpoint for this lane and process the XML entities
        # Getting a list of [(sample, artifact, reagent_label_name), ...]
        demux_list = lib.demultiplexing.get_demux_artifact(lims, lane_artifact)

        # Convert reagent label name into a tuple of (index1, index2) sequences
        index_pairs = get_index_sequences(lims, [reagent_label_name for _, _, reagent_label_name in demux_list])

        # Check that the index lengths are compatible with the configured cycles, and that the
        # indexes within a lane are the same length.
        for index_read in [1,2]:
            index_lengths = set(len(index_pair[index_read-1]) for index_pair in index_pairs)
            if len(index_lengths) != 1:
                warning_flag = True
                logging.warning(f"Different index{index_read} lenghts in lane {lane_id}: {index_lengths}.")
            configured_cycles = process.udf[f"Index {index_read} Cycles"]
            if any(index_length > configured_cycles for index_length in index_lengths):
                # We fail hard, as this can be fixed easily by the user by increasing the cycles
                raise ValueError(f"An index sequence in lane {lane_id} is longer than the configured length: "
                                 f"Index read length: {configured_cycles}. Index length found: {next(iter(index_lengths))}.")

        if not check_index_compatibility(index_pairs, barcode_mismatches):
            raise ValueError(f"The indexes in lane {lane_id} are too similar, see log for details and adjust BarcodeMismatches.")

        # Loop over the unique samples (indexes) in this lane
        for (sample, artifact, _), (index1, index2) in zip(demux_list, index_pairs):
            logging.info(f"Adding sample {sample.name} / artifact ID {artifact.id}.")
            override_cycles = get_override_cycles(
                        process.udf['Read 1 Cycles'],
                        process.udf['Read 2 Cycles'],
                        process.udf['Index 1 Cycles'],
                        process.udf['Index 2 Cycles'],
                        len(index1),
                        len(index2)
                    )
            bclconvert_rows.append({
                'lane': lane_id,
                'sample': sample,
                'artifact': artifact,
                'index1': index1,
                'index2': index2,
                'override_cycles': override_cycles,
                'barcode_mismatches': barcode_mismatches
            })
            if sample.project.udf['Project type'] != "Diagnostics":
                has_any_non_diag_samples = True
            analysis_type = sample.udf.get('NovaSeqX Secondary Analysis')
            if analysis_type == 'DragenGermline-Settings-1.0':
                logging.info(f"Enable DragenGermline standard settings for this sample.")
                analysis_strings[dragen_germline_standard_settings].append(artifact.id)
            # ... add more preset analysis types here?
            elif analysis_type.lower().replace("-", "") == 'adhoc':
                sample.udf.get('NovaSeqX Secondary Analysis Settings')
                # Ad-hoc analysis type should contain the application name in square brackets and all required options.
                # [DragenGermline]SoftwareVersion=0;AppVersion=1;KeepFastQ=FALSE
                analysis = str(sample.udf['NovaSeqX Secondary Analysis'])
                if analysis.startswith('[') and ']' in analysis:
                    logging.info(f"Enable ad-hoc analysis: {analysis}.")
                    analysis_strings[analysis].append(artifact.id)


    # Parse the analysis configuration strings and structure them by app name
    app_configs = defaultdict(dict)
    for analysis_string, samplesheet_sample_ids in analysis_strings.items():
        matches = re.match(r"\[([A-Z-a-z]+)\](.*)$", analysis_string)
        if matches:
            app = matches.group(1)
            app_configs[app].append({
                'settings': matches.group(2),
                'sample_ids': samplesheet_sample_ids
            })
        

    analysis_configs = []
    for analysis_string, samplesheet_sample_ids in analysis_strings.items():
        matches = re.match(r"\[([A-Z-a-z]+)\](.*)$", analysis_string)
        if matches:
            analysis = {'name': matches.group(1)}
            if analysis['name'] in have_apps:
                print(f"Error: Cannot configure multiple analyses for app: {matches.group(1)}.")
                sys.exit(1)
            logging.info(f"Preparing analysis block for: {analysis['name']}.")
            analysis['settings'] = []
            analysis['sample_ids'] = list(set(samplesheet_sample_ids))
            analysis_configs.append(analysis)
            have_apps.add(analysis['app'])

    # generate template
    variables = {
            'library_tube_strip_id': library_tube_strip_id,
            'fastq_compression_format': "gzip" if has_any_non_diag_samples else "dragen",
            'process': process,
            'bclconvert_rows': sorted(bclconvert_rows, key=operator.itemgetter('lane')),
            'dragen_germline_rows': dragen_germline_rows,
            'ad_hoc_analyses': []
    }
    template_dir = os.path.dirname(os.path.realpath(__file__))
    samplesheet_data = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir)) \
                            .get_template('samplesheet-template.csv.j2').render(variables)

    # The file name is based on the library strip ID
    # library_tube_strip_id is checked above, should be safe for a file name
    output_file_name = library_tube_strip_id + ".csv"

    # Upload to LIMS
    output_samplesheet_artifact = Artifact(lims, id=output_samplesheet_luid)
    try:
        output_samplesheet_artifact.get()
    except Exception as e:
        raise RuntimeError(f"Unable to fetch output artifact for sample sheet {output_samplesheet_luid}: {e}.")
    upload_samplesheet(lims, output_samplesheet_artifact, output_file_name, samplesheet_data)

    # Write to shared storage sample sheet folder
    instrument_dir = "".join([c for c in process.udf['NovaSeq X Instrument'] if c.isalpha()]).lower()
    write_samplesheet_path = f"/boston/runScratch/NovaSeqX/SampleSheets/{instrument_dir}/{output_file_name}"
    with open(write_samplesheet_path, "w") as output_file:
        output_file.write(samplesheet_data)

    return warning_flag


if __name__ == "__main__":
    if len(sys.argv) <3:
        print(f"Usage: {sys.argv[0]} PROCESS_ID SAMPLESHEET_ARTIFACT_LUID LOG_FILE_NAME")
        sys.exit(1)
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(level=log_level, filename=sys.argv[3])
    try:
        warning_flag = generate_saample_sheet(sys.argv[1], sys.argv[2])
    except Exception as e:
        logging.exception("Exception caught:")
        print(str(e))
        logging.info("Attempting to remove file from SampleSheet placeholder due to error")
        lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
        output_samplesheet_artifact = Artifact(lims, id=sys.argv[2])
        clear_samplesheet(output_samplesheet_artifact)
        logging.info("Script completed with error.")
        sys.exit(1)
    if warning_flag:
        print("Script completed with warnings. Sample sheet will probably not work. See log.")
        sys.exit(1)
    else:
        logging.info("Script completed successfully.")


