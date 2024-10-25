#!/bin/env python3

# Script to post demultiplexing stats to LIMS.

import os
import re
import glob
import logging
from logging.handlers import TimedRotatingFileHandler
import argparse
from xml.etree.ElementTree import ElementTree
import pandas as pd
import datetime
import json
import yaml
import math
import collections
from genologics.lims import *
from genologics import config
from lib import demultiplexing

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

LOG_FILE_PATH = '/var/log/lims/novaseq-x-demultiplexing-update-lims.log'

DEMULTIPLEXING_PROCESS_TYPE = "BCL Convert Demultiplexing 1.0"
DEMULTIPLEXING_WORKFLOW_NAME = "BCL Convert Demultiplexing 1.0"

RUN_STORAGES = ["/data/runScratch.boston/NovaSeqX"]
RUN_FOLDER_MATCH = r"\d{8}_LH[0-9\-_]+"

IMPORT_FILE_NAME = "ClarityLIMSImport_NSC.yaml"

# Use this to cache demultiplexings of lanes. They are used in two functions.
demux_cache = {}

# Function to configure logging
def configure_logging():
    log_level = "INFO"

    # Create a timed rotating file handler to log to the specified log file
    file_handler = TimedRotatingFileHandler(LOG_FILE_PATH, when='midnight', backupCount=5)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)  # Log everything to the file

    # Create a console handler to log only warnings and higher to stderr
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.WARNING)  # Log only warnings and higher to the console

    # Configure the root logger
    logging.basicConfig(level=log_level, handlers=[file_handler, console_handler])


def get_demux_artifact(artifact):
    """Memoised version of get_demux_artifact"""
    
    global demux_cache
    if artifact.id not in demux_cache:
        demux_cache[artifact.id] = demultiplexing.get_demux_artifact(lims, artifact)
    return demux_cache[artifact.id]


def well_id_to_lane(well_id):
    return int(well_id[0])


def get_lane_input(lane, inputs):
    for well_id, input in inputs:
        if well_id_to_lane(well_id) == lane:
            return input
    raise ValueError(f"No input found for lane {lane}.")


def get_stepconf_and_workflow(workflow_name, process_type_name):
    """Based on the workflow name, look up the protocol step ID, which is the
    same as the queue ID.

    Returns the Step configuration object and the Queue object."""

    workflows = lims.get_workflows(name=workflow_name)
    assert len(workflows) == 1, f"Expected exactly one workflow with name {workflow_name}, got {len(workflows)}"
    for stepconf in workflows[0].protocols[0].steps:
        if stepconf.name == process_type_name:
            return stepconf, workflows[0]
    else:
        raise RuntimeError(f"Cannot find the queue for workflow '{workflow_name}', process type '{process_type_name}'.")



def get_output_lanes(demultiplex_stats):
    """Based on the demultiplexing stats, get a list of lanes that were processed.
    
    This will fail if a lane actually has 0 reads."""

    lane_sums = demultiplex_stats.groupby('Lane').sum()
    nonzero_lanes = lane_sums[lane_sums['# Reads'] > 0]
    return list(nonzero_lanes.index)

# Some important data are stored in the output artifact and then used to create the yaml file.
# The following dict is used to hold information for un-indexed samples. It's necessary because
# these samples don't have any output artifact at all.
dummy_outputs_for_unindexed_lanes = {}

def update_lims_output_info(process, demultiplex_stats, quality_metrics, detailed_summary, num_read_phases):
    global dummy_outputs_for_unindexed_lanes
    lane_total_read_counts = {
        lane: demultiplex_stats[demultiplex_stats['Lane'] == lane]['# Reads'].sum().item()
        for lane in demultiplex_stats['Lane'].unique()
    }

    # Update stats for each input-output pair, representing a unique indexed sample
    # on a lane
    updated_artifacts = []
    for i, o in process.input_output_maps:
        lane_artifact = i['uri']

        lane_id = well_id_to_lane(lane_artifact.location[1])
        if o is None:
            # Create a dummy artifact for this lane with a 'udf' property
            logging.info(f"Input {lane_artifact.id} has a mapping with no output. Using a dummy output to hold data internally in this script.")
            output_artifact = collections.namedtuple("DummyOutput", ["udf"])
            # We have no way to know the original sample ID. Sorry, we just use the NSC sample ID schema here. We couldn't possibly
            # get the UUID for a diag sample.
            samplesheet_sampleid = lane_artifact.samples[0].name + "_" + lane_artifact.id
            output_artifact.udf = {'SampleSheet Sample_ID': samplesheet_sampleid}
            dummy_outputs_for_unindexed_lanes[i['limsid']] = output_artifact
        else:
            # Only process demultiplexed artifacts, not shared outputs like files.
            if o['output-generation-type'] != 'PerReagentLabel': continue
            output_artifact = o['uri']
            logging.info(f"Updating output metrics for indexed sample {output_artifact.name} (lane {lane_id}).")
    
            if "SampleSheet Sample_ID" in output_artifact.udf:
                samplesheet_sampleid = output_artifact.udf["SampleSheet Sample_ID"]
                logging.info(f"Looking up artifact {output_artifact.name} in metrics files by SampleSheet Sample_ID '{samplesheet_sampleid}'.")
            else:
                raise RuntimeError(f"The output artifact {output_artifact.id}, with name {output_artifact.name} didn't have "
                                 "a 'SampleSheet Sample_ID' UDF. This will break things downstream, aborting.")

        # Update the output artifact with the demultiplexing stats
        sample_demux_stats = demultiplex_stats[
                                        (demultiplex_stats['Lane'] == lane_id) & 
                                        (demultiplex_stats['SampleID'] == samplesheet_sampleid)
                                        ]
        # In rare cases there may be more than one demultiplexed artifact with the same
        # sample ID. We aggregate the stats for all of them.

        # There is always a row in quality_metrics for each data read, identified by
        # ReadNumber. The first selection below includes both reads. If fastq output is disabled,
        # there will be no quality_metrics file.
        if quality_metrics is not None:
            sample_quality_metrics = quality_metrics[
                                            (quality_metrics['Lane'] == lane_id) & 
                                            (quality_metrics['SampleID'] == samplesheet_sampleid)
                                            ]
        read_count = sample_demux_stats['# Reads'].sum().item()

        if read_count > 0:
            logging.info(f"Found nonzero read count for {samplesheet_sampleid}, quality metrics: {quality_metrics is not None}")
            output_artifact.udf['# Reads'] = read_count * num_read_phases
            output_artifact.udf['# Reads PF'] = read_count * num_read_phases
            output_artifact.udf['% of PF Clusters Per Lane'] = \
                            read_count / lane_total_read_counts[lane_id] * 100
            output_artifact.udf['% Perfect Index Read'] = \
                            sample_demux_stats['# Perfect Index Reads'].item() / read_count * 100
            output_artifact.udf['% One Mismatch Reads (Index)'] = \
                            sample_demux_stats['# One Mismatch Index Reads'].item() / read_count * 100
            if quality_metrics is not None:
                output_artifact.udf['Yield PF (Gb)'] = sample_quality_metrics['Yield'].sum().item() / 1e9        
                output_artifact.udf['% Bases >=Q30'] = \
                                sample_quality_metrics['YieldQ30'].sum().item() * 100 / max(1, sample_quality_metrics['Yield'].sum().item())
                # empirically, the following value can be NaN if there are no reads. We can't put NaN into LIMS
                mean_q_score = sample_quality_metrics['Mean Quality Score (PF)'].mean()
                if not math.isnan(mean_q_score):
                    output_artifact.udf['Ave Q Score'] = mean_q_score
        else:
            logging.info(f"Found zero read count for {samplesheet_sampleid} and will set everything to 0.")
            output_artifact.udf['# Reads'] = 0
            output_artifact.udf['# Reads PF'] = 0
            output_artifact.udf['Yield PF (Gb)'] = 0    
            output_artifact.udf['% of PF Clusters Per Lane'] = 0
            output_artifact.udf['% Perfect Index Read'] = 0
            output_artifact.udf['% One Mismatch Reads (Index)'] = 0
            output_artifact.udf['% Bases >=Q30'] = 0
            output_artifact.udf['Ave Q Score'] = 0

        # Add number of read 1, read 2 etc. (single read / paired end / weird 10x stuff)
        if quality_metrics is not None:
            output_artifact.udf['Number of data read passes'] = sample_quality_metrics['ReadNumber'].nunique()

        if detailed_summary is not None:
            # Get workflow info for this sample
            # Save the pipeline type and compression type used for this sample
            workflow_all_samples = [
                            (workflow, sample)
                            for workflow in detailed_summary['workflows']
                            for sample in workflow['samples']
                            ]
            workflow_info = [
                            (i, workflow['workflow_name'], sample['ora_compression'])
                            for i, (workflow, sample) in enumerate(workflow_all_samples)
                            if sample['sample_id'] == samplesheet_sampleid
                            ]
            if len(workflow_info) == 1:
                logging.info(f"Workflow info found for {samplesheet_sampleid}: {workflow_info}.")
                # TODO this way of getting the Sample Sheet position (S-number) will probably not work in case of
                # multiple analysis types.
                output_artifact.udf['Sample sheet position'] = workflow_info[0][0] + 1
                output_artifact.udf['Onboard analysis type'] = workflow_info[0][1]
                output_artifact.udf['ORA compression'] = workflow_info[0][2] == "completed"
            else:
                logging.info(f"Have detailed_summary but didn't find workflow info for {samplesheet_sampleid}.")
        else:
            logging.info(f"Skipping workflow info, as there's no detailed_summary.")

        updated_artifacts.append(output_artifact)
     
    # Update artifacts, but skip dummy
    lims.put_batch([o for o in updated_artifacts if isinstance(o, Artifact)])


def update_lims_lane_metrics(process, demultiplex_stats):
    """Update lane-level metrics, on the input artifacts of the process.
    
    The lane information is primarily populated in the run monitoring script.
    This script adds the undetermined percentage."""

    for i in process.all_inputs(unique=True):
        lane_id = well_id_to_lane(i.location[1])
        logging.info(f"Updating lane metrics for lane {lane_id}.")
        lane_demux_stats = demultiplex_stats[demultiplex_stats['Lane'] == lane_id]
        lane_total_read_count = lane_demux_stats['# Reads'].sum()
        lane_undetermined_read_count = lane_demux_stats[lane_demux_stats['SampleID'] == 'Undetermined']['# Reads'].sum()
        if lane_total_read_count > 0:
            i.udf['NSC % Undetermined Indices (PF)'] = lane_undetermined_read_count / lane_total_read_count * 100
        
    lims.put_batch(process.all_inputs(unique=True))


def parse_bclconvert_info_log(infolog_path):
    """Parse the log to get the software version.

    Return the version string."""

    with open(infolog_path) as infolog:
        for line in infolog:
            version_match = re.match(r".*\sSoftwareVersion = (.*)$", line)
            if version_match:
                return version_match.group(1)
        else:
            raise RuntimeError("Info.log does not contain the software version.")



def update_lims_process(process, analysis_dir, run_id, analysis_id, detailed_summary):
    """Update the process with the status and the date of completion."""

    # Info.log is created by onboard DRAGEN and stand-alone BCLConvert, but is not present in onboard 
    # analysis if fastq output is disabled
    # Path for onboard analysis:
    bc_info_log = os.path.join(analysis_dir, "Data", "BCLConvert", "fastq", "Logs", "Info.log")
    if os.path.exists(bc_info_log):
        bcl_convert_version = parse_bclconvert_info_log(bc_info_log)
    elif detailed_summary: # Detailed summary is available when running in onboard mode
        bcl_convert_version = detailed_summary['software_version']
    else:
        bcl_convert_version = "UNKNOWN"
    logging.info(f"BCLConvert version detected: {bcl_convert_version}.")

    process.udf['Run ID'] = run_id
    process.udf['Analysis ID'] = analysis_id
    process.udf['BCL Convert Version'] = bcl_convert_version
    if detailed_summary:
        process.udf['Status'] = detailed_summary['result'].upper()
        process.udf['Compute platform'] = 'Onboard DRAGEN'
    else:
        process.udf['Status'] = 'COMPLETED'
        process.udf['Compute platform'] = 'UNKNOWN'
    process.udf['LIMS import completed on'] = str(datetime.datetime.now())
    process.put()


def get_input_artifacts(rp_tree):
    """Get the input artifacts of the run based on the library tube strip ID."""

    consumable_infos = rp_tree.findall("ConsumableInfo/ConsumableInfo")
    for consumable_info in consumable_infos:
        try:
            if consumable_info.find("Type").text == "SampleTube":
                lts_id = consumable_info.find("SerialNumber").text
                logging.info(f"Found ID {lts_id}.")
                containers = lims.get_containers(name=lts_id, type=["Library 2-tube Strip NSC", "Library 8-tube Strip"])
                if len(containers) == 1:
                    logging.info(f"Found container {containers[0]}.")
                    return list(containers[0].placements.values())
                else:
                    raise RuntimeError(f"Incorrect number of containers named '{lts_id}': {len(containers)}")
        except AttributeError: # Ignore missing things in the XML payload
            pass
    return None


def get_sample_identity_matching(process):
    """Retrieves the sample/project naming, index information and LIMS identifiers
    for the samples in this analysis.

    Returns a list of sample_info dicts, one for each sample for each lane.
    """
    global dummy_outputs_for_unindexed_lanes

    sample_list = []
    for i, o in process.input_output_maps:
        lane_artifact = i['uri']
        lane_id = well_id_to_lane(lane_artifact.location[1])
        demux = get_demux_artifact(lane_artifact)

        sample_info = {'lane': lane_id, 'lane_artifact': lane_artifact.id}
        # Only process demultiplexed artifacts. There will however be one input-output-map with
        # no "o" if the lane has no indexes.
        if o is None:
            output = dummy_outputs_for_unindexed_lanes[i['limsid']]
            sample_info['output_artifact_id'] = None
            output_reagent_label = None
            assert len(lane_artifact.samples) == 1, f"Un-indexed artifact should have a single sample, found {len(lane_artifact.samples)}."
            sample = lane_artifact.samples[0]
        elif o['output-generation-type'] == 'PerReagentLabel':
            output = o['uri']
            sample_info['output_artifact_id'] = o['limsid']
            output_reagent_label = next(iter(o['uri'].reagent_labels))
            for i_sample, demux_artifact, _ in demux:
                if demux_artifact.reagent_labels == o['uri'].reagent_labels:
                    assert len(demux_artifact.samples) == 1, f"In output {o['uri'].id}: Expect demux artifact to have exactly one sample"
                    sample = i_sample
                    break
            else: # Throw if the loop doesn't break
                raise RuntimeError(f"Unable to determine the sample object for output artifact {o['uri'].id}.")
            if o['uri'].samples != [sample]:
                logging.warn(f"Found wrong samples {o['uri'].samples} on output artifact {o['uri'].id} due to LIMS demultiplexing step bug.")
                o['uri'].name = sample.name + " (name corrected by script)"
                o['uri'].put()
        else: # This is some other output like a log file etc., skip it
            continue

        sample_info['sample_id'] = sample.id
        sample_info['sample_name'] = sample.name
        sample_info['project_id'] = sample.project.id
        sample_info['project_name'] = sample.project.name
        sample_info['project_type'] = sample.project.udf.get('Project type')
        sample_info['delivery_method'] = sample.project.udf.get('Delivery method')

        # The onboard analysis type and number of data reads is set above in update_lims_output_info
        onboard_analysis = output.udf.get('Onboard analysis type')
        if onboard_analysis:
            sample_info['onboard_workflow'] = onboard_analysis
            sample_info['ora_compression'] = output.udf['ORA compression']
            sample_info['samplesheet_position'] = output.udf['Sample sheet position']
        # Check if the number of data reads has been recorded
        if 'Number of data read passes' in output.udf:
            sample_info['num_data_read_passes'] = output.udf['Number of data read passes']

        # Locate the demultiplexed artifact with the same reagent label as the output
        # of this step. This may be used as Sample_ID in the sample sheet..
        for sample, demux_artifact, dem_reagent_label in demux:
            if dem_reagent_label == output_reagent_label:
                sample_info['artifact_id'] = demux_artifact.id
                sample_info['artifact_name'] = demux_artifact.name
                sample_info['samplesheet_sample_id'] = output.udf['SampleSheet Sample_ID']
                break
        sample_list.append(sample_info)

    return sample_list



def complete_step(step):
    """Advance the step until completion."""

    logging.info("Completing step " + step.id)
    for na in step.actions.next_actions:
        na['action'] = 'complete'
    step.actions.put()
    fail = False
    while not fail and step.current_state.upper() != "COMPLETED":
        logging.debug("Advancing the step...")
        step.advance()
        step.get(force=True)
    logging.info("Completed " + step.id + ".")


def process_analysis(run_dir, analysis_dir):
    """Import demultiplexing analysis results from DRAGEN Onboard."""

    # Find the LIMS artifacts of this run
    logging.info(f"Looking for artifacts.")
    try:
        rp_tree = ElementTree()
        rp_tree.parse(os.path.join(run_dir, "RunParameters.xml"))
        logging.info(f"Loaded RunParameters.xml in {run_dir} to look for library tube strip ID.")
        run_artifacts = get_input_artifacts(rp_tree)
    except Exception as e:
        logging.warn(f"Error while getting input artifacts: {e}.")
        return
    if not run_artifacts:
        logging.info("There are no artifacts for this run, skipping.")
        return

    run_artifact_limsids = [a.id for a in run_artifacts]
    logging.info(f"Run artifacts are: {', '.join(run_artifact_limsids)}.")
    
    analysis_id = os.path.basename(analysis_dir)
    run_id = os.path.basename(run_dir)

    # Demultiplex_Stats.csv is available in the Demux directory and in the BCLConvert directory.
    # If FASTQ output is not requested, the BCLConvert directory may not exist, but we can get
    # Demultiplex_stats anyway
    demux_report_path = os.path.join(analysis_dir, "Data", "Demux", "Demultiplex_Stats.csv")
    if not os.path.isfile(demux_report_path):
        logging.error(f"Missing file {demux_report_path} - unable to process the analysis.")
        return
    demultiplex_stats = pd.read_csv(demux_report_path)
    # Use the file to determine the lane set used for analysis
    analysis_lanes = set(demultiplex_stats['Lane'])
    logging.info(f"Analysis '{analysis_id}' includes lanes: {','.join(str(l) for l in sorted(analysis_lanes))}.")

    # Find artifacts for this analysis
    process = None
    analysis_artifacts = []
    for a in run_artifacts:
        if well_id_to_lane(a.location[1]) in analysis_lanes:
            analysis_artifacts.append(a)
    if analysis_artifacts:
        logging.info(f"Found artifacts for this analysis: {analysis_artifacts}.")
    else:
        logging.error("None of the Run artifacts have locations matching the lane IDs. Skipping this analysis.")
        return

    # There should always be an existing step created by the sample sheet generator
    processes = lims.get_processes(inputartifactlimsid=[a.id for a in analysis_artifacts], type=DEMULTIPLEXING_PROCESS_TYPE)
    logging.info(f"BCL Convert processes matching the input artifacts: {processes}.")
    processes = [p for p in processes if p.udf.get("Status") == "PENDING"]
    logging.info(f"PENDING BCL Convert processes matching the input artifacts: {processes}.")
    for test_process in processes:
        if set(test_process.all_inputs()) == set(analysis_artifacts):
            logging.info(f"Using process {test_process.id}, which has an exact overlap with the analysis artifacts.")
            process = test_process
            step = Step(lims, id=process.id)
        else:
            logging.info(f"Skipping {test_process.id} input artifacts {test_process.all_inputs()} because of mismatch with analysis lanes")

    if not process: # No existing process
        raise RuntimeError(f"Didn't find any BCL Convert process for Analysis {analysis_id} in run {run_id}")


    # Import demultiplexing quality metrics. They will be in the App configured for the specific sample.
    # The *fastq component is designed to also match "ora_fastq".
    qmetrics_paths = glob.glob(os.path.join(analysis_dir, "Data", "*", "*fastq", "Reports", "Quality_Metrics.csv"))
    if qmetrics_paths:
        quality_metrics = pd.concat([
            pd.read_csv(qmetrics_path)
            for qmetrics_path in qmetrics_paths
            ])
    else:
        # If fastq output is deselected, no quality metrics are available here.
        quality_metrics = None

    # Import detailed summary (Onboard analysis)
    # Use glob for DRAGEN version directory name
    detailed_summary_paths = glob.glob(os.path.join(analysis_dir, "Data", "summary", "*", "detailed_summary.json"))
    if len(detailed_summary_paths) == 1:
        with open(detailed_summary_paths[0]) as ds:
            detailed_summary = json.load(ds)
    elif len(detailed_summary_paths) == 0:
        detailed_summary = None
    else:
        raise RuntimeError("Found multiple detailed_summary.json, but there should only be one.")

    # We need to get the number of data reads (single read / paired end), because the '# Reads PF' UDF should be reported
    # as reads per end. This info is contained in Quality_Metrics.csv, but we base it on RunParameters.xml because we may
    # not always have Quality_Metrics.
    num_read_phases = sum( # Get length
            1
            for node in rp_tree.findall("PlannedReads/Read")
            if node.attrib['ReadName'].startswith("Read") # Read1, Read2
            )
    if quality_metrics is not None:
        qm_num_read_phases = quality_metrics['ReadNumber'].nunique()
        if num_read_phases != qm_num_read_phases:
            logging.warn(f"Number of read passes in RunParameters.xml ({num_read_phases}) and Quality_Metrics.csv "
                    f"({qm_num_read_phases}) don't match. Using Quality_Metrics.csv number.")
            # There can be a mismatch if OverrideCycles is used to change the meaning of some reads. Then
            # Quality_Metrics.csv will have the correct value.
            num_read_phases = qm_num_read_phases

    logging.info(f"Updating output (per index) metrics and details.")
    update_lims_output_info(process, demultiplex_stats, quality_metrics, detailed_summary, num_read_phases)
    logging.info(f"Updating lane metrics.")
    update_lims_lane_metrics(process, demultiplex_stats)
    logging.info(f"Updating global process-level details.")
    update_lims_process(process, analysis_dir, run_id, analysis_id, detailed_summary)
    logging.info(f"Prepare a list of sample identities.")
    sample_id_list = get_sample_identity_matching(process)

    complete_step(step)
    limsfile_path = os.path.join(analysis_dir, IMPORT_FILE_NAME)
    with open(limsfile_path, "w") as ofile:
        yaml.dump({
            'status': 'ImportCompleted',
            'bcl_convert_version': process.udf['BCL Convert Version'],
            'compute_platform': process.udf['Compute platform'],
            'demultiplexing_process_id': process.id,
            'run_id': run_id,
            'samples': sample_id_list
            }, ofile)

def find_and_process_runs():
    run_dirs = [r
            for directory in RUN_STORAGES
            for r in glob.glob(os.path.join(directory, "*_*_*"))
            if re.match(RUN_FOLDER_MATCH, os.path.basename(r))
            ]

    logging.info(f"Found {len(run_dirs)} run directories")

    for run_dir in run_dirs:
        run_id = os.path.basename(run_dir)
        logging.info(f"Processing analyses of run {run_id}")
        analysis_dirs = [
                    adir for adir in glob.glob(os.path.join(run_dir, "Analysis", "*"))
                    if os.path.isdir(adir)
                ]
        # There may be multiple analysis directories if the processing has been requeued.
        # The analyses may be handling different lanes, so we should import all, not just
        # the newest.
        for analysis_dir in analysis_dirs:
            analysis_id = os.path.basename(analysis_dir)
            logging.info(f"Processing analysis {analysis_id}")

            limsfile_path = os.path.join(analysis_dir, IMPORT_FILE_NAME)
            if os.path.exists(limsfile_path):
                logging.info(f"Skipping analysis {analysis_id} because {IMPORT_FILE_NAME} exists.")
                continue
            if not os.path.exists(os.path.join(analysis_dir, "CopyComplete.txt")):
                logging.info(f"Analysis {analysis_id} does not have CopyComplete.txt. Skipping.")
                continue

            # We will process this analysis or die trying, so we mark it as processed.
            logging.info(f"Analysis {analysis_id} is ready for LIMS import. Creating {IMPORT_FILE_NAME}.")
            with open(limsfile_path, "w") as ofile:
                ofile.write("{'status': 'ImportStarted'}")

            process_analysis(run_dir, analysis_dir)


def main():
    configure_logging()
    logging.info(f"Executing NovaSeq X demultiplexing monitoring at {datetime.datetime.now()}")

    try:
        find_and_process_runs()
    except Exception:
        logging.exception("Uncaught exception in cron job")

    logging.info(f"Completed NovaSeq X demultiplexing monitoring at {datetime.datetime.now()}")


if __name__ == '__main__':
    main()

