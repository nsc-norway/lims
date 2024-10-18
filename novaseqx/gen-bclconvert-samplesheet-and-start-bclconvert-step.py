# this
import datetime
import logging
import operator
import os
import sys
import time
import uuid

import jinja2

import lib.demultiplexing
from genologics import config
from genologics.lims import *

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

DEMULTIPLEXING_PROCESS_TYPE = "BCL Convert Demultiplexing 1.0"
DEMULTIPLEXING_WORKFLOW_NAME = "BCL Convert Demultiplexing 1.0w"
SEQUENCING_PROCESS_TYPE = "AUTOMATED - Sequencing Run NovaSeqX AMG 1.0"
LOAD_LIBRARY_TUBE_PROCESS_TYPE = "Load to Library Tube Strip NovaSeqX AMG"


def get_stepconf_and_workflow(workflow_name, process_type_name):
    """Based on the workflow name, look up the protocol step ID, which is the
    same as the queue ID.

    Returns the Step configuration object and the Queue object."""

    workflows = lims.get_workflows(name=workflow_name)
    assert (
        len(workflows) == 1
    ), f"Expected exactly one workflow with name {workflow_name}, got {len(workflows)}"
    for stepconf in workflows[0].protocols[0].steps:
        if stepconf.name == process_type_name:
            return stepconf, workflows[0]
    else:
        raise RuntimeError(
            f"Cannot find the queue for workflow '{workflow_name}', process type '{process_type_name}'."
        )


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

    # First retrieve all reagent labels, using batches to avoid URL size limit
    reagent_types = []
    BATCH_SIZE = 100
    for batch_start in range(0, len(reagent_label_list), BATCH_SIZE):
        reagent_types += lims.get_reagent_types(
            name=[
                name
                for name in reagent_label_list[batch_start : (batch_start + BATCH_SIZE)]
                if name
            ]
        )

    # This will fetch all reagent types from API one by one, by querying for the "name" property
    reagent_type_map = {rt.name: rt for rt in reagent_types}

    result_index_list = []
    for reagent_label in reagent_label_list:
        if not reagent_label:
            result_index_list.append(("", ""))
        else:
            if reagent_label in reagent_type_map:
                seq_parts = reagent_type_map[reagent_label].sequence.split("-")
                if len(seq_parts) == 1:  # Single index
                    result_index_list.append((seq_parts[0], ""))
                elif len(seq_parts) == 2:  # Dual index
                    result_index_list.append(tuple(seq_parts))
                else:
                    raise ValueError(
                        f"Reagent type {reagent_label} has malformed sequence in LIMS: {reagent_type_map[reagent_label].sequence}."
                    )
            else:
                raise ValueError(
                    f"Reagent type {reagent_label} referenced in artifact but does not exist."
                )

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
        for index1_other, index2_other in index_pair_list[i + 1 :]:
            index1_mismatches = hamming_distance(index1, index1_other)
            index2_mismatches = hamming_distance(index2, index2_other)

            # The samples can be distinguished if the mismatch count in either index is
            # greater than the allowed mismatches plus one.
            index1_ok = index1_mismatches > difference_threshold
            index2_ok = index2_mismatches > difference_threshold
            if (not index1_ok) and (not index2_ok):
                index_display = "-".join([i for i in [index1, index2] if i])
                index_other_display = "-".join([i for i in [index1, index2] if i])
                logging.warning(
                    f"Index {index_display} is too similar to {index_other_display}. "
                    f"Index1 mismatches: {index1_mismatches}, index2 mismatches: {index2_mismatches}."
                )
                logging.warning(
                    f"With {maximum_allowed_mismatches} allowed mismatches, the difference shoud be "
                    f"greater than {difference_threshold} differences."
                )
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
        override_string += ";"
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


def parse_settings(settings_string):
    """The settings are specified as a semicolon-separated string. The first element contains the
    app name, but before the app name, it can optionally contain a configuration name followed by colon.
    The following items are key-value pairs separated by equals signs.

    DiagWgsSettings_1.0:DragenGermline;AppVersion=1.0.0;SoftwareVersion=4.1.23;ReferenceGenomeDir=hg38-alt_masked.cnv.hla.rna-8-1667496521-2;MapAlignOutFormat=cram;KeepFastQ=true;VariantCallingMode=AllVariantCallers

    The function returns a normalized tuple representation of this configuration. The first element of the
    return value is the App name. The second element is a tuple of tuples for the list of key-value pairs.

    return AppName, (
        (Setting1, SettingValue1),
        (Setting2, SettingValue2),
        ...
    )
    """

    parts = settings_string.split(";")
    app_name = parts[0].split(":")[-1]
    if "=" in app_name:
        raise ValueError(
            f"Incorrect analysis string: The first element (app name) contains 'equals sign': '{app_name}'."
        )

    kv_list = []
    for part in parts[1:]:
        kv = part.split("=", maxsplit=1)
        if len(kv) == 1:
            raise ValueError(
                f"Incorrect settings element '{part}' in analysis string: Does not contain equals sign (key=value)."
            )
        kv_list.append(tuple(kv))

    if len(set(k for k, _ in kv_list)) < len(kv_list):
        raise ValueError(
            "There appears to be a duplicate setting in the analysis string for this sample. Only specify each setting once."
        )

    return app_name, tuple(kv_list)


def get_sample_id(datasetuuid, sample, artifact, enable_sampleproject_directories):
    """Get the string that is used as Sample_ID in the sample sheet. """

    if sample.project.udf.get("Project type") == "Diagnostics":
        split = sample.project.name.split("-")
        if len(split) >= 2:
            batch_id = split[1]
        else:
            batch_id = sample.project.name
        dna_id = sample.name.split("-")[0]
        sample_id = "_".join([batch_id, dna_id, datasetuuid])
        return sample_id
    elif enable_sampleproject_directories:
        return sample.name
    else:
        return sample.name + "_" + artifact.id


def generate_sample_sheet_start_bclconvert(
    is_redemultiplexing, sample_sheet_process, output_samplesheet_luid
):
    warning_flag = False
    # Store SampleID and UUID for setting on the BCL convert step
    # Key: (lane_artifact_id, reagent_labels)
    # Value: (datasetuuid, sample_id)
    sample_uuid_sampleid = dict()
    logging.info(
        f"Generating NovaSeq X SampleSheet file for process {sample_sheet_process.id} and will upload to artifact ID {output_samplesheet_luid}"
    )

    if is_redemultiplexing:
        # Re-demultiplex NovaSeq X run process
        # Get the input Analyte artifact, corresponding to lanes of the flow cell
        lane_artifacts = sample_sheet_process.all_inputs()

        assert all(
            la.parent_process
            and la.parent_process.type_name.startswith(LOAD_LIBRARY_TUBE_PROCESS_TYPE)
            for la in lane_artifacts
        ), f"Can only re-demultiplex the DERIVED SAMPLES of {LOAD_LIBRARY_TUBE_PROCESS_TYPE} step"

        load_tube_process = lane_artifacts[0].parent_process
    else:
        # Load to Library Tube Strip process
        # Get the output Analyte artifact, corresponding to lanes of the flow cell
        output_artifacts = process.all_outputs(unique=True, resolve=True)
        lane_artifacts = [o for o in output_artifacts if o.type == 'Analyte']
        # There is just one process, Load to Library Tube Strip, for the first demultiplexing
        load_tube_process = sample_sheet_process

    logging.info(
        f"Load tube process is {load_tube_process.id}, sample sheet process is {sample_sheet_process.id}."
    )

    # Get and pre-cache all the samples, to determine analysis types etc.
    samples = lims.get_batch([s for a in lane_artifacts for s in a.samples])

    # Set the Run name to a fixed pattern
    if not is_redemultiplexing and load_tube_process.udf["Run Name"] == "(Set automatically)":
        # Get the first component of the project names: Diag, or the last name of NSC users
        project_names_set = set(
                sample.project.name.split("-")[0]
                for sample in samples
                )
        project_names_list = []
        if "Diag" in project_names_set:
            project_names_set.remove("Diag")
            project_names_list = ["Diag"]
        project_names_list += sorted(project_names_set)
        project_string = "-".join(project_names_list)
        # Get the date
        date_string = datetime.datetime.now().strftime("%Y-%m-%d")
        # Flow cell side - only available on Load to Library Tube step
        fc_side = load_tube_process.udf['Planned Flow Cell Side']
        load_tube_process.udf['Run Name'] = "_".join([date_string, fc_side, project_string])
        logging.info(
            f"Defining Run Name: {load_tube_process.udf['Run Name']}"
        )
        # The process will be PUT at the end of the script to update the field in LIMS.
        # If we fail before then, the run name is not updated.

    # Check flow cell type compatibility
    flowcell_type = load_tube_process.udf["Flow Cell Type"]
    container = next(iter(lane_artifacts)).location[
        0
    ]  # Placement script assures that there is just one container
    container_size = container.type.y_dimension["size"]
    if flowcell_type in ["10B", "25B"]:
        if container_size != 8:
            raise ValueError(
                f"Flow cell type {flowcell_type} requested, container size should be 8, but is {container_size}."
            )
    elif flowcell_type == "1.5B":
        if container_size != 2:
            raise ValueError(
                f"Flow cell type 1.5B requested, container size should be 2, but is {container_size}."
            )
    else:
        logging.warning(f"Unknown Flow Cell Type '{flowcell_type}'.")

    # Get the library tube strip ID
    library_tube_strip_id = container.name
    # This check is important to prevent writing unexpected files - see output file below
    assert all(
        (c.isalnum() or c in ["-"]) for c in library_tube_strip_id
    ), "Illegal characters in library strip tube name"

    # Determine whether the platform supports Sample_Project column (Project directories)
    bcl_convert_instrument = process.udf["BCL Convert Instrument"]
    enable_sampleproject_column = bcl_convert_instrument != "Onboard DRAGEN"

    # Process each lane and produce BCLConvert and DragenGermline sample tables
    bclconvert_rows = []

    # This list will contain tuples of (sample_id, (app, settings))
    # (app, settings) is a parsed tuple structure from the UDF NovaSeqX Secondary Analysis string
    analysis_settings = []

    # Store sample UUID keyed by (sample.id, artifact.id) so the same UUID is used for the same
    # sample when it's run on multiple lanes. The "artifact" is the uniquely demultiplexed
    # ancestor artifact returned by the demux endpoint, reprensenting a single unique reagent_label.
    sample_uuids_map = {}

    for lane_artifact in sorted(
        lane_artifacts, key=lambda artifact: artifact.location[1][0]
    ):
        # Get lane from well position e.g. B:1 is lane 2.
        lane_id = int(lane_artifact.location[1].split(":")[0])
        barcode_mismatches = lane_artifact.udf["BarcodeMismatches"]

        logging.info(
            f"Processing lane {lane_id}, artifact {lane_artifact.name}. Barcode mismatches = {barcode_mismatches}."
        )

        # Get the demux endpoint for this lane and process the XML entities
        # Getting a list of [(sample, artifact, reagent_label_name), ...]
        demux_list = lib.demultiplexing.get_demux_artifact(lims, lane_artifact)

        # Convert reagent label name into a tuple of (index1, index2) sequences
        index_pairs = get_index_sequences(
            lims, [reagent_label_name for _, _, reagent_label_name in demux_list]
        )

        # Check that the index lengths are compatible with the configured cycles, and that the
        # indexes within a lane are the same length.
        for index_read in [1, 2]:
            index_lengths = set(len(index_pair[index_read - 1]) for index_pair in index_pairs)
            if len(index_lengths) != 1:
                logging.info(
                    f"Different index{index_read} lengths in lane {lane_id}: {index_lengths}. This is not a problem."
                )
            original_cycles = load_tube_process.udf[f"Index {index_read} Cycles"]
            configured_cycles = sample_sheet_process.udf[f"Index {index_read} Cycles"]
            if configured_cycles != original_cycles:
                # can be that the original setting was wrong, so just give a warning
                logging.warning(
                    f"The original Index {index_read} Cycles was {original_cycles}; different from current Index {index_read} Cycles: {configured_cycles}"
                )
            if any(index_length > configured_cycles for index_length in index_lengths):
                # We fail hard, as this can be fixed easily by the user by increasing the cycles
                raise ValueError(
                    f"An index sequence in lane {lane_id} is longer than the configured length: "
                    f"Index read length: {configured_cycles}. Index length found: {next(iter(index_lengths))}."
                )

        if not check_index_compatibility(index_pairs, barcode_mismatches):
            raise ValueError(
                f"The indexes in lane {lane_id} are too similar, see log for details and adjust BarcodeMismatches."
            )

        # Loop over the unique samples (indexes) in this lane
        for (sample, artifact, _), (index1, index2) in zip(demux_list, index_pairs):
            # Get / Create UUID and Sample ID
            if (sample.id, artifact.id) in sample_uuids_map:
                datasetuuid = sample_uuids_map[(sample.id, artifact.id)]
            else:
                datasetuuid = str(uuid.uuid4())
                sample_uuids_map[(sample.id, artifact.id)] = datasetuuid
            sample_id = get_sample_id(datasetuuid, sample, artifact, enable_sampleproject_column)
            assert not "," in sample_id, "Comma not allowed in sample name."
            logging.info(
                f"Adding sample {sample.name} / artifact ID {artifact.id}. Sample_ID in SampleSheet: {sample_id}."
            )
            # Configure index reads
            override_cycles = get_override_cycles(
                sample_sheet_process.udf["Read 1 Cycles"],
                sample_sheet_process.udf["Read 2 Cycles"],
                sample_sheet_process.udf["Index 1 Cycles"],
                sample_sheet_process.udf["Index 2 Cycles"],
                len(index1),
                len(index2),
            )
            # Check how many index reads and set BarcodeMismatches to "na" if the index read is not used
            barcode_mismatches_read = [
                barcode_mismatches if index_seq else "na"
                for index_seq in [index1, index2]
            ]
            # Output a sample sheet row
            bclconvert_rows.append(
                {
                    "lane": lane_id,
                    "sample_id": sample_id,  # The sample ID should be determined here, not in the template, for consistency w analysis
                    "sample": sample,
                    "artifact": artifact,
                    "index1": index1,
                    "index2": index2,
                    "override_cycles": override_cycles,
                    "barcode_mismatches_1": barcode_mismatches_read[0],
                    "barcode_mismatches_2": barcode_mismatches_read[1],
                    "sample_project": sample.project.name # Always added to the list, but only used if enable_sampleproject_column.
                }
            )
            sample_uuid_sampleid[(lane_artifact.id, tuple(artifact.reagent_labels))] = (datasetuuid, sample_id)

            # This option is only avaiable for Re-demultiplexing. For the initial sample sheet, this is defaulted to False.
            bclconvert_only = sample_sheet_process.udf.get("Demultiplexing Only")

            if not bclconvert_only:
                if bcl_convert_instrument != "Onboard DRAGEN":
                    logging.warning("The option 'Demultiplexing Only' should only be enabled if running on Onboard DRAGEN.")
                    warning_flag = True

                analysis_string = sample.udf.get("NovaSeqX Secondary Analysis")
                if analysis_string:
                    logging.info(
                        f"Sample {sample.name} has UDF NovaSeqX Secondary Analysis = '{analysis_string}'."
                    )
                    analysis = parse_settings(analysis_string)
                    analysis_settings.append((sample_id, analysis))
                    logging.info(
                        f"Sample {sample.name} will be analysed with app {analysis[0]} with {len(analysis[1:])} settings."
                    )

    # The following three lists contain one element per analysis type (App)
    analysis_settings_blocks = []
    analysis_data_blocks = []
    analysis_data_block_headers = []
    analysis_apps = []

    logging.info(
        "Finished demultiplexing settings, will prepare analysis settings. Note that you can edit the sample's 'NovaSeqX Secondary Analysis' field now if there are any problems."
    )

    # Process each unique app block
    for app in set(app for _, (app, _) in analysis_settings):
        samples_settings = [
            (sample_id, settings)
            for sample_id, (element_app, settings) in analysis_settings
            if element_app == app
        ]
        # Get all settings keys seen
        settings_keys = {
            key
            for (sample_id, settings) in samples_settings
            for (key, value) in settings
        }
        logging.info(
            f"Preparing app {app} with settings keys {', '.join(settings_keys)}."
        )
        # De-duplicate samples and add missing keys, so all samples have all keys.
        # Preserves the order of samples in the original list.
        samples_settings_unique_complete = {}
        for sample_id, settings in samples_settings:
            dictify = dict(settings)
            full_settings_dict = {key: dictify.get(key, "na") for key in settings_keys}
            prev_settings = samples_settings_unique_complete.get(sample_id)
            if not prev_settings:
                samples_settings_unique_complete[sample_id] = full_settings_dict
            elif prev_settings != full_settings_dict:
                raise RuntimeError(
                    f"Sample id {sample_id} has two different analysis configurations: {full_settings_dict} != {prev_settings}."
                )

        # Place settings in the headers or the data block depending on whether they have different values
        data_block_keys = []
        settings_block = []
        for key in settings_keys:
            first_sample_value = next(iter(samples_settings_unique_complete.values()))[
                key
            ]
            if all(
                sample_settings[key] == first_sample_value
                for sample_id, sample_settings in samples_settings_unique_complete.items()
            ):
                settings_block.append((key, first_sample_value))
            else:
                data_block_keys.append(key)
        for required_header_field in ["AppVersion", "SoftwareVersion"]:
            if required_header_field in data_block_keys:
                raise RuntimeError(
                    f"There are different values for {required_header_field} among the samples queued for app {app}, but only a single value is supported."
                )
            if required_header_field not in [k for k, v in settings_block]:
                raise RuntimeError(
                    f"The analysis settings must contain field {required_header_field}, but it is not specified for app {app}."
                )

        logging.info(
            f"There are {len(samples_settings_unique_complete)} samples queued for {app}."
        )

        # Construct the data block as a list of lists
        data_block = []
        for sample_id, sample_settings in samples_settings_unique_complete.items():
            data_block.append(
                [sample_id] + [sample_settings[k] for k in data_block_keys]
            )

        # Save the config for this app in the global lists
        analysis_settings_blocks.append(settings_block)
        analysis_data_block_headers.append(["Sample_ID"] + data_block_keys)
        analysis_data_blocks.append(data_block)
        analysis_apps.append(app)
        logging.info(
            f"Added {len(settings_block)} shared settings and {len(data_block_keys)} per-sample settings for {app}."
        )

    # generate template
    variables = {
        "library_tube_strip_id": library_tube_strip_id,
        "process": sample_sheet_process,
        "enable_sampleproject_column": enable_sampleproject_column,
        "bclconvert_rows": sorted(bclconvert_rows, key=operator.itemgetter("lane")),
        "analyses_zipped": zip(
            analysis_apps,
            analysis_settings_blocks,
            analysis_data_block_headers,
            analysis_data_blocks,
        )
    }
    template_dir = os.path.dirname(os.path.realpath(__file__))
    samplesheet_data = (
        jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
        .get_template("samplesheet-template.csv.j2")
        .render(variables)
    )

    # The file name is set as <run-name>_<strip-id>
    # (strip ID is sanitised above, by crashing if it contains invalid characters)
    safe_run_name = "".join(
        [
            c
            for c in sample_sheet_process.udf["Run Name"]
            if (c.isalnum() or c in "-_.,")
        ]
    )
    output_file_name = (
        "_".join([safe_run_name, library_tube_strip_id]) + ".csv"
    )

    # Upload to LIMS
    output_samplesheet_artifact = Artifact(lims, id=output_samplesheet_luid)
    try:
        output_samplesheet_artifact.get()
    except Exception as e:
        raise RuntimeError(
            f"Unable to fetch output artifact for sample sheet {output_samplesheet_luid}."
        ) from e
    upload_samplesheet(
        lims, output_samplesheet_artifact, output_file_name, samplesheet_data
    )

    # PUT the process to save the run name
    if not is_redemultiplexing:
        load_tube_process.put()

    if bcl_convert_instrument == "Onboard DRAGEN":
        # Write to shared storage sample sheet folder
        instrument_dir = "".join(
            [c for c in sample_sheet_process.udf["NovaSeq X Instrument"] if c.isalpha()]
        ).lower()
        assert len(instrument_dir) > 0
        write_samplesheet_path = (
            f"/boston/runScratch/NovaSeqX/SampleSheets/{instrument_dir}/{output_file_name}"
        )
        with open(write_samplesheet_path, "w") as output_file:
            output_file.write(samplesheet_data)

    try:
        start_bclconvert_process(sample_sheet_process, lane_artifacts, sample_uuid_sampleid)
    except Exception:
        warning_flag = True
        logging.exception("Exception when creating BCL Convert process:")

    return warning_flag


def start_bclconvert_process(sample_sheet_process, bclconvert_inputs, samplesheet_sample_ids):
    """
    Queue artifacts and create a process.
    """

    bclconvert_id = sample_sheet_process.udf.get("BCL Convert LIMS-ID")
    bclconvert_process = None
    if bclconvert_id:
        bclconvert_process = Process(lims, id=bclconvert_id)
        logging.info(
            f"Recycling existing process of type '{DEMULTIPLEXING_PROCESS_TYPE}' with ID '{bclconvert_process.id}'."
        )
        try:
            bclconvert_process.get()
        except:
            logging.warn(f"Unable to fetch Process '{bclconvert_process.id}', will create a new one instead.")
            bclconvert_process = None
    if bclconvert_process is None:
        stepconf, workflow = get_stepconf_and_workflow(
            DEMULTIPLEXING_WORKFLOW_NAME, DEMULTIPLEXING_PROCESS_TYPE
        )
        logging.info(
            f"Queue the artifacts for {DEMULTIPLEXING_WORKFLOW_NAME} and start a step."
        )
        lims.route_analytes(bclconvert_inputs, workflow)
        time.sleep(1)  # artifact not in queue error sometimes
        bclconvert_step = lims.create_step(stepconf, bclconvert_inputs)
        bclconvert_process = Process(lims, id=bclconvert_step.id)
        sample_sheet_process.udf["BCL Convert LIMS-ID"] = bclconvert_step.id
        sample_sheet_process.udf["BCL Convert LIMS-ID"] = bclconvert_step.id
        sample_sheet_process.put()
        logging.info("Started process %s", bclconvert_process)

    # update bclconvert process UDFs
    bclconvert_process.udf["Compute platform"] = sample_sheet_process.udf[
        "BCL Convert Instrument"
    ]
    bclconvert_process.udf["BCL Convert Version"] = sample_sheet_process.udf[
        "Onboard DRAGEN BCL Convert Version"
    ]
    # Enable for Overview page
    bclconvert_process.udf["Monitor"] = True

    # Run ID from the sequencing step
    sequencing_steps = lims.get_processes(
        inputartifactlimsid=[a.id for a in bclconvert_inputs],
        type=SEQUENCING_PROCESS_TYPE,
    )
    if sequencing_steps:
        latest_seq = sequencing_steps[-1]  # There should only be one seq step (rerun would use a new container)
        assert isinstance(latest_seq, Process)
        bclconvert_process.udf["Run ID"] = latest_seq.udf["Run ID"]
        # Copying the Sequencing Output Folder was removed, because the seq step provides a network UNC-like path,
        # not valid on the Linux cluster.
        # If we need to support multiple output locations, we can copy it here and translate it here or in the
        # Run Demultiplexing automation.

    # PENDING initially; update to RUNNING or ACTIVE or SUCCESS by lims updating script Onboard/Extenal DRAGEN
    bclconvert_process.udf["Status"] = "PENDING"

    bclconvert_process.put()

    outputs_to_put = []
    # store samplesheet sample id
    for inputinfo, outputinfo in bclconvert_process.input_output_maps:
        i = inputinfo["uri"]
        # Skip null outputs. When there is a single sample without index, the 
        # output will be null and we can't set any ID.
        if outputinfo is None: continue
        o = outputinfo["uri"]
        # Skip common outputs, like files, if that comes up
        if outputinfo["output-generation-type"] == "PerReagentLabel":
            _dataset_uuid, _sample_id = samplesheet_sample_ids[(i.id, tuple(o.reagent_labels))]
            logging.info(
                "Update 'SampleSheet Sample_ID' and 'Dataset UUID' UDFs for %s to '%s' and '%s'",
                o,
                _sample_id,
                _dataset_uuid
            )
            o.udf["SampleSheet Sample_ID"] = _sample_id
            o.udf["Dataset UUID"] = _dataset_uuid
            outputs_to_put.append(o)
    lims.put_batch(outputs_to_put)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            f"Usage: {sys.argv[0]} MODE PROCESS_ID SAMPLESHEET_ARTIFACT_LUID LOG_FILE_NAME"
        )
        sys.exit(1)

    mode = sys.argv[1]
    if mode not in ["redemultiplexing", "loadtubestrip"]:
        print(
            f"The mode should be one of: [redemultiplexing, loadtubestrip], not '{mode}'."
        )
        sys.exit(1)
    is_redemultiplexing = mode == "redemultiplexing"

    process_id = sys.argv[2]
    output_samplesheet_luid = sys.argv[3]

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=log_level, filename=sys.argv[4])

    process = Process(lims, id=process_id)
    try:
        warning_flag = generate_sample_sheet_start_bclconvert(
            is_redemultiplexing, process, output_samplesheet_luid
        )
    except Exception as e:
        logging.exception("Exception caught:")
        print(str(e))

        logging.info(
            "Attempting to remove file from SampleSheet placeholder due to error"
        )
        output_samplesheet_artifact = Artifact(lims, id=output_samplesheet_luid)
        clear_samplesheet(output_samplesheet_artifact)
        logging.info("Script completed with error.")
        sys.exit(1)

    if warning_flag:
        print(
            "Script completed with warnings. Sample sheet will probably not work. See log."
        )
        sys.exit(1)

    logging.info("Script completed successfully.")

