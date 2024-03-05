#!/bin/env python3

# Script to post demultiplexing stats to LIMS.

import os
import logging
import argparse
from xml.etree.ElementTree import ElementTree
import pandas as pd
import datetime
from genologics.lims import *
from genologics import config
from lib import demultiplexing

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

NOVASEQ_RUN_PROCESS_TYPE = "AUTOMATED - NovaSeq X Run AMG 1.0"
DEMULTIPLEXING_WORKFLOW_NAME = "Demultiplexing AMG 3.0"

# Get the Run ID from the run folder. BCL convert copies RunInfo.xml to the Reports
# folder under the output folder.
def get_run_id(bclconvert_output_folder):
    run_info_xml_path = os.path.join(bclconvert_output_folder, 'Reports', 'RunInfo.xml')
    tree = ElementTree()
    tree.parse(run_info_xml_path)
    flowcell_id = tree.find('Run/Flowcell').text
    return flowcell_id


def get_process_by_run_id(run_id):
    processes = lims.get_processes(type=NOVASEQ_RUN_PROCESS_TYPE, udf={'Run ID': run_id})
    if len(processes) == 0:
        raise ValueError(f"No process found with Run ID {run_id}.")
    if len(processes) > 1:
        logging.warning(f"Multiple sequencing processes found with Run ID {run_id}. Using the last one.")
    return processes[-1]


def well_id_to_lane(well_id):
    return int(well_id[0])


def get_lane_input(lane, inputs):
    for well_id, input in inputs:
        if well_id_to_lane(well_id) == lane:
            return input
    raise ValueError(f"No input found for lane {lane}.")


def get_output_lanes(demultiplex_stats):
    """Based on the demultiplexing stats, get a list of lanes that were processed.
    
    This will fail if a lane actually has 0 reads."""

    lane_sums = demultiplex_stats.groupby('Lane').sum()
    nonzero_lanes = lane_sums[lane_sums['# Reads'] > 0]
    return list(nonzero_lanes.index)lims.put_batch([process])e) + process.all_outputs(unique=True))

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


def update_lims_with_analysis(process, reports_dir):

    demultiplex_stats = pd.read_csv(os.path.join(reports_dir, 'Demultiplex_Stats.csv'))
    quality_metrics = pd.read_csv(os.path.join(reports_dir, 'Quality_Metrics.csv'))
    update_lims_process(process)
    update_lims_output_metrics(process, demultiplex_stats, quality_metrics)
    update_lims_lane_metrics(process, demultiplex_stats, quality_metrics)


def main(bclconvert_folder, process_id=None):
    logging.info(f"Updating demultiplexing stats from {bclconvert_folder} to LIMS process {process_id}.")

    # Get the inputs of the process and determine the lanes
    inputs = process.all_inputs(unique=True, resolve=True)
    if len(set(input.location[0].id for input in inputs)) != 1:
        raise ValueError(f"Multiple input containers were detected for process {process_id}.")
    lane_inputs = [(well_id_to_lane(input.location[1]), input) for input in inputs]
    lanes = [lane for lane, _ in lane_inputs]
    logging.info(f"Found lanes {lanes} in the LIMS.")

    # Get the demultiplexing stats from the Stats.json file
    stats_file = os.path.join(bclconvert_folder, 'Stats.json')
    if not os.path.exists(stats_file):
        raise ValueError("Stats.json not found in the output folder.")
    with open(stats_file, 'r') as f:
        stats = yaml.safe_load(f)

    # The demultiplexing job may not be configured to process all lanes. We loop over the
    # lanes found in the Stats file and update only those in LIMS.
    for lane in stats['Lanes']:
        pass




if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Script to update LIMS after demultiplexing.')
    parser.add_argument('bclconvert-output-folder', required=True, help='Path to the output folder of BCL Convert OR the run folder.')
    parser.add_argument('--run-process-id', help='LIMS process ID of the sequencing run process (e.g. 24-1111) - use if auto-detection fails.')
    args = parser.parse_args()

    main(args.bclconvert_output_folder, args.run_process_id)
