#!/bin/env python3

# Script to post demultiplexing stats to LIMS.

import os
import re
import glob
import logging
import argparse
from xml.etree.ElementTree import ElementTree
import pandas as pd
import datetime
import json
from genologics.lims import *
from genologics import config
from lib import demultiplexing

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

DEMULTIPLEXING_PROCESS_TYPE = "BCL Convert Demultiplexing 0.9"
DEMULTIPLEXING_WORKFLOW_NAME = "BCL Convert Demultiplexing 1.0"

RUN_STORAGES = ["/data/runScratch.boston/NovaSeqX"]
RUN_FOLDER_MATCH = r"\d{8}_LH[0-9\-_]+"


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


    #lims.put_batch([process])e) + process.all_outputs(unique=True))


def update_lims_output_metrics(process, demultiplex_stats, quality_metrics):
    lane_total_read_counts = {
        lane: demultiplex_stats[demultiplex_stats['Lane'] == lane]['# Reads'].sum()
        for lane in demultiplex_stats['Lane'].unique()
    }

    # Update stats for each input-output pair, representing a unique indexed sample
    # on a lane
    demux_cache = {}
    updated_artifacts = []
    for i, o in process.input_outputs_maps:
        lane_artifact = i['uri']
        output_artifact = o['uri']
        lane_id = well_id_to_lane(input.location[1])
        logging.info(f"Updating output metrics for {output_artifact.name} (lane {lane_id}).")
    
        if lane_id not in demux_cache:
            demux_cache[lane_id] = demultiplexing.get_demux_artifact(lims, lane_artifact)
        
        # Locate the demultiplexed artifact with the same reagent label as the output
        # of this step
        for _, demux_artifact, _ in demux_cache[lane_id]:
            if demux_artifact.reagent_labels == output_artifact.reagent_labels:
                demux_artifact_id = demux_artifact.id
                break
        else:
            # Unable to find the demultiplexed artifact. We set an invalid ID, so the
            # update will fail.
            demux_artifact_id = None

        # Update the output artifact with the demultiplexing stats
        sample_demux_stats = demultiplex_stats[
                                        (demultiplex_stats['Lane'] == lane_id) & 
                                        (demultiplex_stats['sample_id'] == demux_artifact_id)
                                        ]
        # In rare cases there may be more than one demultiplexed artifact with the same
        # sample ID. We aggregate the stats for all of them.
        # There is always a row in quality_metrics for each data read, identified by
        # ReadNumber. The first selection below includes both reads.
        sample_quality_metrics = quality_metrics[
                                        (quality_metrics['Lane'] == lane_id) & 
                                        (quality_metrics['sample_id'] == demux_artifact_id)
                                        ]
        read_count = sample_demux_stats['# Reads'].sum()
        if read_count > 0:
            output_artifact.udf['# Reads'] = read_count
            output_artifact.udf['# Reads (PF)'] = read_count
            output_artifact.udf['Yield PF (Gb)'] = sample_quality_metrics['Yield'].sum() / 1e9        
            output_artifact.udf['% of PF Clusters Per Lane'] = \
                            read_count / lane_total_read_counts[lane_id] * 100
            output_artifact.udf['% Perfect Index Reads'] = \
                            sample_demux_stats['# Perfect Index Reads'] / read_count * 100
            output_artifact.udf['% One Mismatch Reads (Index)'] = \
                            sample_demux_stats['# One Mismatch Index Reads'] / read_count * 100
            output_artifact.udf['% Bases >=Q30'] = \
                            sample_quality_metrics['Yield Q30'].sum() / sample_quality_metrics['Yield'].sum() * 100
            output_artifact.udf['Ave Q Score'] = sample_quality_metrics['Mean Quality Score (PF)'].mean()
        else:
            output_artifact.udf['# Reads'] = 0
            output_artifact.udf['# Reads (PF)'] = 0
            output_artifact.udf['Yield PF (Gb)'] = 0    
            output_artifact.udf['% of PF Clusters Per Lane'] = 0
            output_artifact.udf['% Perfect Index Reads'] = 0
            output_artifact.udf['% One Mismatch Reads (Index)'] = 0
            output_artifact.udf['% Bases >=Q30'] = 0
            output_artifact.udf['Ave Q Score'] = 0

        updated_artifacts.append(output_artifact)
     
    lims.put_batch(updated_artifacts)


def update_lims_lane_metrics(process, demultiplex_stats):
    """Update lane-level quality metrics, on the input artifacts of the process.
    
    The lane information is primarily populated in the run monitoring script.
    This script adds the undetermined percentage."""

    for i in process.all_inputs(unique=True):
        lane_id = well_id_to_lane(i.location[1])
        logging.info(f"Updating lane metrics for lane {lane_id}.")
        lane_demux_stats = demultiplex_stats[demultiplex_stats['Lane'] == lane_id]
        lane_total_read_count = lane_demux_stats['# Reads'].sum()
        lane_undetermined_read_count = lane_demux_stats[lane_demux_stats['sample_id'] == 'Undetermined']['# Reads'].sum()
        if lane_total_read_count > 0:
            i.udf['NSC % Undetermined Indices (PF)'] = lane_undetermined_read_count / lane_total_read_count * 100
        
    lims.put_batch(process.all_inputs(unique=True))


def update_lims_process(process, bcl_convert_root_dir):
    """Update the process with the status and the date of completion."""

    fastq_complete = os.path.join(bcl_convert_root_dir, 'Logs', 'FastqComplete.txt')
    bcl_convert_version = "UNKNOWN"
    try:
        with open(fastq_complete, 'r') as f:
            for line in f:
                if line.startswith('bcl-convert Version '):
                    # Expected line:
                    #bcl-convert Version 00.000.000.4.2.7
                    # The version is then 4.2.7.
                    dummy_prefix = "00.000.000."
                    bcl_convert_version = line.split()[-1]
                    if bcl_convert_version.startswith(dummy_prefix):
                        bcl_convert_version = bcl_convert_version[len(dummy_prefix):]
                    break
    except IOError:
        pass

    process.udf['BCL Convert Version'] = bcl_convert_version
    process.udf['Status'] = 'Completed'
    process.udf['LIMS import completed'] = datetime.datetime.now()
    process.put()


def get_input_artifacts(run_dir):
    """Get the input artifacts of the run based on the library tube strip ID."""

    rp_tree = ElementTree()
    rp_tree.parse(os.path.join(run_dir, "RunParameters.xml"))
    logging.info(f"Loaded RunParameters.xml in {run_dir} to look for library tube strip ID.")
    consumable_infos = rp_tree.findall("ConsumableInfo/ConsumableInfo")
    for consumable_info in consumable_infos:
        try:
            if consumable_info.find("Type").text == "SampleTube":
                lts_id = consumable_info.find("SerialNumber").text
                logging.info(f"Found ID {lts_id}.")
                containers = lims.get_containers(name=lts_id)
                if len(containers) == 1:
                    logging.info(f"Found container {containers[0]}.")
                    return list(containers[0].placements.values())
                else:
                    raise RuntimeError(f"Incorrect number of containers named '{lts_id}': {len(containers)}.")
        except AttributeError: # Ignore missing things in the XML payload
            pass
    return None


def process_analysis(run_dir, analysis_dir):
    """Import demultiplexing analysis results from DRAGEN Onboard."""

    # Find the LIMS artifacts of this run
    logging.info(f"Looking for artifacts.")
    try:
        run_artifacts = get_input_artifacts(run_dir)
    except Exception as e:
        logging.warn(f"Error while getting input artifacts: {e}.")
        return
    if not run_artifacts:
        logging.info("There are no artifacts for this run, skipping.")
        return

    run_artifact_limsids = [a.id for a in run_artifacts]
    logging.info(f"Run artifacts are: {', '.join(run_artifact_limsids)}.")
    
    analysis_id = os.path.basename(analysis_dir)

    process = None
    # If the analysis ID is 1, there may be an existing step created by the run monitoring script
    if analysis_id == '1':
        logging.info("Analysis ID is '1', looking for open processes created by run monitoring.")
        processes = lims.get_processes(inputartifactlimsid=run_artifact_limsids,
                                    type=DEMULTIPLEXING_PROCESS_TYPE,
                                    udf={'Status':'Waiting','Analysis ID': '1'})
        if len(processes) == 1:
            process = processes[0]
            logging.info(f"Found process {process.id}, will update it.")
        elif len(processes) == 0:
            logging.info(f"No processes match the search criteria, so we will create one instead.")
        else:
            logging.error(f"Unexpectedly found {len(processes)} demux processes for analysis 1, will skip this analysis.")
            return

    if not process:
        # Queue artifacts and create a process. The artifacts cannot be queued if they are already in a
        # demux process. In normal operation, the processes of other analyses should have been closed.
        stepconf, workflow = get_stepconf_and_workflow(DEMULTIPLEXING_WORKFLOW_NAME, DEMULTIPLEXING_PROCESS_TYPE)
        logging.info(f"Will queue the artifacts for {DEMULTIPLEXING_WORKFLOW_NAME} and start a step.")
        lims.route_analytes(run_artifacts, workflow)
        step = lims.create_step(stepconf, run_artifacts)
        process = Process(lims, id=step.id)

    reports_dir = os.path.join(analysis_dir, "Data", "BCLConvert", "fastq", "Reports")
    if os.path.isdir(reports_dir):
        # Import demultiplexing stats
        demultiplex_stats = pd.read_csv(os.path.join(reports_dir, 'Demultiplex_Stats.csv'))
        quality_metrics = pd.read_csv(os.path.join(reports_dir, 'Quality_Metrics.csv'))
        update_lims_process(process)
        update_lims_output_metrics(process, demultiplex_stats, quality_metrics)
        update_lims_lane_metrics(process, demultiplex_stats, quality_metrics)
    else:
        logging.error(f"Missing reports dir {reports_dir} - unable to import QC metrics.")
    

    # Write project information

    



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
        analysis_dirs = glob.glob(os.path.join(run_dir, "Analysis", "*"))
        # There may be multiple analysis directories if the processing has been requeued.
        # The analyses may be handling different lanes, so we should import all, not just
        # the newest.
        for analysis_dir in analysis_dirs:
            analysis_id = os.path.basename(analysis_dir)
            logging.info(f"Processing analysis {analysis_id}")

            limsfile_path = os.path.join(analysis_dir, "ClarityLIMSImport_NSC.json")
            if os.path.exists(limsfile_path):
                logging.info(f"Skipping analysis {analysis_id} because ClarityLIMSImport_NSC.json exists.")
                continue
            if not os.path.exists(os.path.join(analysis_dir, "CopyComplete.txt")):
                logging.info(f"Analysis {analysis_id} does not have CopyComplete.txt. Skipping.")

            # We will process this analysis or die trying, so we mark it as processed.
            logging.info(f"Analysis {analysis_id} is ready for LIMS import. Creating ClarityLIMSImport_NSC.json.")
            with open(limsfile_path, "w") as ofile:
                ofile.write("{'status': 'ImportStarting'}")

            process_analysis(run_dir, analysis_dir)


def main():
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(level=log_level)
    logging.info(f"Executing NovaSeq X demultiplexing monitoring at {datetime.datetime.now()}")


    find_and_process_runs()
    logging.info(f"Completed NovaSeq X demultiplexing monitoring at {datetime.datetime.now()}")




if __name__ == '__main__':

    main()
