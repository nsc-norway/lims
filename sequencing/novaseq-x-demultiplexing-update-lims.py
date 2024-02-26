#!/bin/env python3

# Script to post demultiplexing stats to LIMS.

import glob
import os
import re
import yaml
import math
import logging
import argparse
import datetime
import requests
from xml.etree.ElementTree import ElementTree
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

NOVASEQ_RUN_PROCESS_TYPE = "AUTOMATED - NovaSeq X Run AMG 1.0"
DEMULTIPLEXING_WORKFLOW_NAME = "Demultiplexing AMG 3.0"

# Get the Flowcell ID from the run folder. BCL convert copies RunInfo.xml to the Reports
# folder under the output folder.
def get_flowcell_id(bclconvert_output_folder):
    run_info_xml = glob.glob(os.path.join(bclconvert_output_folder, 'Reports', 'RunInfo.xml'))
    if not run_info_xml:
        raise ValueError("RunInfo.xml not found in the output folder.")
    tree = ElementTree()
    tree.parse(run_info_xml[0])
    flowcell_id = tree.find('Run/Flowcell').text
    return flowcell_id


def well_id_to_lane(well_id):
    return "ABCDEFGH".index(well_id[0]) + 1


def main(bclconvert_folder, process_id=None):

    if process_id:
        process = Process(lims, id=process_id)
    else:
        # Get the Flowcell ID from the output folder
        flowcell_id = get_flowcell_id(bclconvert_folder)
        logging.info(f"Flowcell ID: {flowcell_id}")
        # Find the process ID from the Flowcell ID
        processes = lims.get_processes(type=NOVASEQ_RUN_PROCESS_TYPE, udf={'Flow Cell ID': flowcell_id})
        if len(processes) == 0:
            raise ValueError(f"No process found with Flow Cell ID {flowcell_id}.")
        if len(processes) > 1:
            logging.warning(f"Multiple sequencing processes found with Flow Cell ID {flowcell_id}. Using the last one.")
        process = processes[-1]

    logging.info(f"Updating demultiplexing stats from {bclconvert_folder} to LIMS process {process_id}.")

    # Get the inputs of the process and determine the lanes
    inputs = process.all_inputs(unique=True, resolve=True)
    if len(set(input.location[0].id for input in inputs)) != 1:
        raise ValueError(f"Multiple input containers were detected for process {process_id}.")
    lane_inputs = [(well_id_to_lane(input.location[1]), input) for input in inputs]
    lanes = [lane for lane, _ in lane_inputs]
    logging.info(f"Found lanes {lanes)} in the LIMS.")

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
