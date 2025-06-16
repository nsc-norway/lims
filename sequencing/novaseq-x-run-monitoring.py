#!/usr/bin/python

# Run information update script for NovaSeq X.

# Compared to update-runs.py, it uses a simplistic approach of only relying on LIMS
# to track the run status, no database file used for performance.

import glob
import os
import sys
import re
import yaml
import math
import logging
from logging.handlers import TimedRotatingFileHandler
from dateutil import parser, tz
import datetime
import requests
from xml.etree.ElementTree import ElementTree
from interop import py_interop_run_metrics, py_interop_run, py_interop_summary
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

LOG_FILE_PATH = '/var/log/lims/novaseq-x-run-monitoring.log'

# Load instrument names from config file
INSTRUMENT_NAME_MAP = {seq['id']: seq['name']
            for seq in yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "sequencers.yaml")))
            }

# This script can only handle a single process type and workflow at a time. If there is a
# new version, the script should be updated at the time when the new version is activated.
PROCESS_TYPE_NAME = "AUTOMATED - Sequencing Run NovaSeqX AMG 1.0"
WORKFLOW_NAME = "NovaSeq X 3.0"

RUN_STORAGES=[
    "/data/runScratch.boston/NovaSeqX"
    ]


RUN_FOLDER_MATCH = r"\d{8}_LH[0-9\-_]+"

# The values should correspond to reagent kits in Clarity.
REAGENT_TYPES = {
    'Reagent':  'NovaSeq X Reagent Cartridge',
    'FlowCell': 'NovaSeq X Flow Cell',
    'Buffer':   'NovaSeq X Buffer Cartridge',
    'Lyo':      'NovaSeq X Lyophilization Cartridge',
}

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


def get_library_tube_strip_id(run_parameters_xml):
    """Get the library tube strip ID from the RunParameters.xml file,
    used for matching the container in LIMS. The argument should contain
    an ElementTree object with the parsed XML.
    
    Returns the library tube strip ID, or None if not found."""

    consumable_infos = run_parameters_xml.findall("ConsumableInfo/ConsumableInfo")
    for consumable_info in consumable_infos:
        try:
            if consumable_info.find("Type").text == "SampleTube":
                return consumable_info.find("SerialNumber").text
        except AttributeError:
            pass
    return None


def get_stepconf_and_queue():
    """Based on the workflow name, look up the protocol step ID, which is the
    same as the queue ID.
    
    Returns the Step configuration object and the Queue object."""

    workflows = lims.get_workflows(name=WORKFLOW_NAME)
    assert len(workflows) == 1, f"Expected exactly one workflow with name {WORKFLOW_NAME}, got {len(workflows)}"
    for stepconf in workflows[0].protocols[0].steps:
        if stepconf.name == PROCESS_TYPE_NAME:
            return stepconf, stepconf.queue()
    else:
        raise RuntimeError(f"Cannot find the queue for workflow '{WORKFLOW_NAME}', process type '{PROCESS_TYPE_NAME}'.")


def get_cycle(total_cycles, run_dir, lower_bound_cycle):
    """Get total cycles and current cycle based on files written in the run folder.
    lower_bound_cycle represents our knowledge of what cycles have already been completed.

    Will look at lane 1 only, to reduce I/O and complexity.

    Returns (current cycle, total cycles).
    """
    
    lower_bound_cycle = max(0, lower_bound_cycle)
    for cycle in range(lower_bound_cycle, total_cycles):
        test_path = os.path.join(run_dir, "Data", "Intensities", "BaseCalls", "L001","C{0}.1".format(cycle+1))
        if not os.path.exists(test_path):
            return cycle

    # All cycles are complete
    return total_cycles


# Helper functions
def set_if_available(process, xml, path, udf):
    node = xml.find(path)
    if node is not None:
         process.udf[udf] = node.text


def set_if_not_nan(artifact, field, value):
    if not math.isnan(value):
        artifact.udf[field] = value


def set_initial_fields(process, run_parameters, run_id):
    """Set fields that are available immediately when RunParameters.xml is available.
    """

    for ide, name in INSTRUMENT_NAME_MAP.items():
        if re.match(r"\d+_%s_.*" % (ide), run_id):
            process.udf['Instrument Name'] = name
            break
    else:
        logging.warn(f"The run ID {run_id} did not match any of the known instruments, "
                     " 'Instrument Name' not set.")
    
    # Set read lengths
    total_cycles = 0
    try:
        for read in run_parameters.findall("PlannedReads/Read"):
            read_name = read.attrib['ReadName']
            cycles = int(read.attrib['Cycles'])
            if read_name == "Read1":    process.udf['Read 1 Cycles'] = cycles
            elif read_name == "Read2":  process.udf['Read 2 Cycles'] = cycles
            elif read_name == "Index1": process.udf['Index 1 Read Cycles'] = cycles
            elif read_name == "Index2": process.udf['Index 2 Read Cycles'] = cycles
            else:
                logging.warning(f"Unknown read name {read_name} in PlannedReads section for {run_id}.")
            total_cycles += cycles
    except (AttributeError, KeyError) as e:
        logging.exception(f"Malformed PlannedRuns section for {run_id} in RunParameters.xml. "
                    "Unable to determine read lengths.")
        total_cycles = 0
    process.udf['Run Status'] = f"Cycle 0 of {total_cycles}"
    process.udf['Current Cycle'] = 0
    process.udf['Total Cycles'] = total_cycles

    # Set standard metadata
    process.udf['Instrument Run ID'] = run_id
    process.udf['Run ID'] = run_id
    if not 'Demultiplexing Process ID' in process.udf:
        process.udf['Demultiplexing Process ID'] = ""
    process.udf['Monitor'] = True # Flag for overview page

    # Set run parameters
    set_if_available(process, run_parameters, 'FlowCellType', 'Flow Cell Type')
    set_if_available(process, run_parameters, 'SystemSuiteVersion', 'System Suite Version')
    set_if_available(process, run_parameters, 'OutputFolder', 'Output Folder')
    set_if_available(process, run_parameters, 'Side', 'Flow Cell Side')
    set_if_available(process, run_parameters, 'InstrumentSerialNumber', 'Instrument ID')
    set_if_available(process, run_parameters, 'InstrumentType', 'Instrument Type')
    set_if_available(process, run_parameters, 'ExperimentName', 'Run Name')
    set_if_available(process, run_parameters, 'Side', 'Flow Cell Side')

    # Even though Flow Cell ID is recorded as a lot, we also record it as a UDF
    # to enable quick searching for processes by Flow Cell ID.
    for consumable_info in run_parameters.findall("ConsumableInfo/ConsumableInfo"):
        if consumable_info.find("Type").text == "FlowCell":
            process.udf['Flow Cell ID'] = consumable_info.find("SerialNumber").text
        elif consumable_info.find("Type").text == "SampleTube":
            process.udf['Library Tube Barcode'] = consumable_info.find("SerialNumber").text


# Start time in RunInfo.xml seems wrong (too late) - we use the one in RunCompletionStatus.xml instead
#def set_start_time(process, run_dir):
#    """Set start time based on RunInfo.xml"""
#
#    try:
#        runinfo_tree = ElementTree()
#        runinfo_tree.parse(os.path.join(run_dir, "RunInfo.xml"))
#        start_time = parser.parse(runinfo_tree.find("Run/Date").text)
#        local_timezone = tz.tzlocal()
#        process.udf['Run Start Time'] = start_time.astimezone(local_timezone).strftime("%Y-%m-%dT%H:%M:%S")
#        logging.debug(f"Set the Run Start Time to {process.udf['Run Start Time']}.")
#    except (IOError, AttributeError):
#        logging.warning(f"Can't get the start time from RunInfo.xml.")


def set_lane_qc(process, run_dir):
    # Get the input-output mappings to find the output artifact for each lane
    lane_artifacts = [] # List of (lane, artifact)
    for i, o in process.input_output_maps:
        if o['output-generation-type'] == 'PerInput':
            try:
                lane_number = int(i['uri'].location[1][0])
            except Exception as e:
                logging.error(f"Error: Could not determine lane number for artifact {i['uri'].id} "
                              f"well location {i['uri'].location[1]}.")
                continue
            lane_artifacts.append((lane_number, o['uri']))

    valid_to_load = py_interop_run.uchar_vector(py_interop_run.MetricCount, 0)
    py_interop_run_metrics.list_summary_metrics_to_load(valid_to_load)
    valid_to_load[py_interop_run.ExtendedTile] = 1
    run_metrics = py_interop_run_metrics.run_metrics()
    run_metrics.read(run_dir, valid_to_load)
    summary = py_interop_summary.run_summary()
    py_interop_summary.summarize_run_metrics(run_metrics, summary)

    read_count = summary.size()
    lane_count = summary.lane_count()

    if lane_count != len(lane_artifacts):
        logging.error(f"Error: Number of lanes in InterOp data: {lane_count}, does not match the number "
            f"of lanes in LIMS: {len(lane_artifacts)}.")
        return

    for (lane_number, artifact) in lane_artifacts:
        artifact.qc_flag = "PASSED"
        lane_index = lane_number - 1
        nonindex_read_count = 0
        for read in range(read_count):
            read_data = summary.at(read)
            if not read_data.read().is_index():
                read_label = str(nonindex_read_count + 1)
                lane_summary = read_data.at(lane_index)
                if math.isnan(lane_summary.yield_g()):
                    continue # Skip if the run failed and didn't start the read
                artifact.udf['Yield PF (Gb) R{}'.format(read_label)] = lane_summary.yield_g()
                artifact.udf['% Bases >=Q30 R{}'.format(read_label)] = lane_summary.percent_gt_q30()
                artifact.udf['Cluster Density (K/mm^2) R{}'.format(read_label)] = lane_summary.density().mean()
                artifact.udf['Reads PF (M) R{}'.format(read_label)] = lane_summary.reads_pf() / 1.0e6
                artifact.udf['%PF R{}'.format(read_label)] = lane_summary.percent_pf().mean()
                artifact.udf['Intensity Cycle 1 R{}'.format(read_label)] = lane_summary.first_cycle_intensity().mean()
                set_if_not_nan(artifact, f'% Error Rate R{read_label}', lane_summary.error_rate().mean())
                set_if_not_nan(artifact, f'% Phasing R{read_label}', lane_summary.phasing().mean())
                set_if_not_nan(artifact, f'% Prephasing R{read_label}', lane_summary.prephasing().mean())
                set_if_not_nan(artifact, f'% Aligned R{read_label}', lane_summary.percent_aligned().mean())
                set_if_not_nan(artifact, f'% Occupied Wells', lane_summary.percent_occupied().median())
                nonindex_read_count += 1
    lims.put_batch([a for _, a in lane_artifacts])


def create_reagent_lots(run_parameters, run_id):
    """Reagent information is imported into Clarity as reagent lots. This function
    reads the ConsumableInfo section of the RunParameters.xml file and creates
    reagent lots in Clarity for each reagent used in the run.

    Returns the lot objects.
    """
    lots = []
    for consumable_info in run_parameters.findall("ConsumableInfo/ConsumableInfo"):
        try:
            serial_number = consumable_info.find("SerialNumber").text
            lot_number = consumable_info.find("LotNumber").text
            # Date format: 2024-09-25T00:00:00+02:00
            expiration_date = parser.parse(consumable_info.find("ExpirationDate").text) # parser is from dateutil
            version = consumable_info.find("Version").text
            name = consumable_info.find("Name").text
            part_number = consumable_info.find("PartNumber").text
            consumable_type = consumable_info.find("Type").text

            reagent_kit_name = REAGENT_TYPES.get(consumable_type)
            if reagent_kit_name:
                logging.info(f"Found ConsumableInfo of type {consumable_type} with serial number {serial_number}.")
                reagent_kits = lims.get_reagent_kits(name=reagent_kit_name)
                if not reagent_kits:
                    logging.error(f"Reagent kit {reagent_kit_name} not found in LIMS.")
                else:
                    note = f"'{name}', ver. '{version}', part '{part_number}', for run {run_id}"
                    for attempt in range(3):
                        try:
                            if attempt > 0:
                                serial_number += f"-{attempt}" # Change the serial number to avoid conflicts
                                logging.info(f"Retrying creating reagent lot for {reagent_kit_name} "
                                             f"with serial number {serial_number}.")
                            lot = lims.create_lot(reagent_kits[0], serial_number, lot_number, 
                                                str(expiration_date.date()), notes=note, status='ACTIVE')
                            logging.info(f"Created reagent lot for kit {reagent_kit_name} with "
                                         f"serial number {serial_number}, lot number {lot_number} "
                                         f"expiration date {expiration_date}, and note '{note}'.")
                            lots.append(lot)
                            break
                        except requests.exceptions.HTTPError as e:
                            logging.error(f"Error creating reagent lot: {e}")
            else:
                logging.info(f"Unknown ConsumableInfo type '{consumable_type}' skipped.")

        except AttributeError:
            logging.exception("Encountered an exception whilst processing ConsumableInfo record.")

    return lots


def set_final_fields(process, run_dir, run_id):
    """Set fields on run completion from RunCompletionStatus.xml."""

    # Set the Run End Time to now as a fallback, to avoid re-processing the run
    process.udf['Run End Time'] = str(datetime.datetime.now())
    process.put()

    try:
        rcs = ElementTree()
        rcs.parse(os.path.join(run_dir, "RunCompletionStatus.xml"))

        # Update Current Cycle
        cycles = 0
        for read in rcs.findall("CompletedReads/Read"):
            cycles += int(read.attrib['Cycles'])
        process.udf['Current Cycle'] = cycles
        process.udf['Run Status'] = rcs.find("RunStatus").text

        start_time = parser.parse(rcs.find("RunStartTime").text)
        local_timezone = tz.tzlocal()
        process.udf['Run Start Time'] = start_time.astimezone(local_timezone).strftime("%Y-%m-%dT%H:%M:%S")

        end_time = parser.parse(rcs.find("RunEndTime").text)
        process.udf['Run End Time'] = end_time.astimezone(local_timezone).strftime("%Y-%m-%dT%H:%M:%S")
    except (IOError, AttributeError):
        logging.exception("An error occurred while trying to update the final run information.")


def complete_step(step):
    """Advance the step until completion."""

    logging.info("Finishing process " + step.id)
    # This is a custom function in the NSC version of the client library. Sorry.
    lims.set_default_next_step(step)
    fail = False
    while not fail and step.current_state.upper() != "COMPLETED":
        logging.debug("Advancing the step...")
        step.advance()
        step.get(force=True)
    logging.info("Completed " + step.id + ".")


def main():
    logging.info(f"Executing NovaSeq X run monitoring at {datetime.datetime.now()}")

    run_dirs = [r
            for directory in RUN_STORAGES
            for r in glob.glob(os.path.join(directory, "*_*_*"))
            if re.match(RUN_FOLDER_MATCH, os.path.basename(r))
            ]
    
    logging.info(f"Found {len(run_dirs)} run directories")

    # Cache for the step configuration object and Queue object
    stepconf = None
    queue = None

    for run_dir in run_dirs:
        run_id = os.path.basename(run_dir)
        logging.info(f"Processing run {run_id}")

        # Load the RunParameters.xml file, which contains the library tube strip ID used
        # for matching the container in LIMS.
        try:
            rp_tree = ElementTree()
            rp_tree.parse(os.path.join(run_dir, "RunParameters.xml"))
        except IOError:
            logging.info(f"Run {run_id} does not have a RunParameters.xml file, skipping.")
            continue
        
        library_tube_strip_id = get_library_tube_strip_id(rp_tree)
        if library_tube_strip_id is None:
            logging.warning(f"Run {run_id} does not have a library tube strip ID, skipping.")
            continue
        logging.info(f"Run {run_id} has library tube strip ID {library_tube_strip_id}.")

        # Check that the Run ID in the xml file and the run folder name match
        rp_run_id = rp_tree.find("RunId").text
        if rp_run_id != run_id:
            logging.error(f"Run ID in RunParameters.xml {rp_run_id} does not match the run "
                          f"folder name {run_id}.")
            continue

        lims_containers = lims.get_containers(name=library_tube_strip_id)
        if not lims_containers:
            logging.info(f"Run {run_id} does not have a matching container '{library_tube_strip_id}' in "
                            "LIMS, skipping.")
            continue
        
        # Get one of the artifacts in the container
        analyte = next(iter(lims_containers[-1].placements.values()))
        # Look for run processes in LIMS
        processes = lims.get_processes(inputartifactlimsid=[analyte.id], type=PROCESS_TYPE_NAME)

        # Get the process, or start a new one if not available. These branches should both set
        # the process and the step variables.
        if processes:
            process = processes[-1]
            step = Step(lims, id=process.id)
            logging.info(f"Found {len(processes)} processes for run {run_id} in LIMS. Will use "
                            f"process {process.id}.")
        else:
            logging.info(f"Run {run_id} does not have a matching process in LIMS, checking queues.")
            if queue is None:
                stepconf, queue = get_stepconf_and_queue()
            container_artifacts = set(lims_containers[-1].placements.values())
            queue_artifacts = set(queue.artifacts)
            if not queue_artifacts >= container_artifacts:
                logging.info(f"All artifacts of {run_id} are not in the queue for {PROCESS_TYPE_NAME}. "
                             "The run will not be processed.")
                continue
            logging.info(f"All artifacts of {run_id} found in queue, starting step.")
            step = lims.create_step(stepconf, container_artifacts)
            process = Process(lims, id=step.id)


        # New run - set information
        if process.udf.get('Run ID') is None:
            logging.info(f"Setting initial fields for run {run_id}.")
            set_initial_fields(process, rp_tree, run_id)
            process.put()

            logging.info(f"Creating and setting reagent lots for run {run_id}.")
            lots = create_reagent_lots(rp_tree, run_id)
            logging.info(f"Created {len(lots)} lots. Setting used lots on the step.")
            step.reagentlots.set_reagent_lots(lots)
            step.reagentlots.put()

        # We now have a run folder and a matching Process in LIMS. We get the run status
        # from the run folder.
        
        # Determine if run has already been marked as finished, by checking the End Time
        if not process.udf.get('Run End Time'):

            # Match the cycle count to keep track of total cycles
            logging.info(f"Getting the cycle count to update progress.")
            old_cycle = process.udf['Current Cycle']
            total_cycles = process.udf['Total Cycles']
            current_cycle = get_cycle(total_cycles, run_dir, old_cycle)
            if current_cycle != old_cycle:
                process.udf['Run Status'] = f"Cycle {current_cycle} of {total_cycles}"
                process.udf['Current Cycle'] = current_cycle
                process.put()
            
            # Determine if the run is finished
            copy_complete = os.path.exists(os.path.join(run_dir, "CopyComplete.txt"))
            if copy_complete:
                logging.info(f"Run {run_id} sequencing is recently completed and copied, "
                                "updating QC metrics.")
                set_lane_qc(process, run_dir)
                logging.info("Updated lane QC information, now setting fields for run completion.")
                set_final_fields(process, run_dir, run_id)
                process.put()

                # Complete the sequencing step when the run is finsihed.
                complete_step(step)

                # Set the UDF on the container, for use by the overview page
                # Under normal operation, there should only be one library tube strip container.
                lims_containers[-1].udf['Recently completed'] = True
                lims_containers[-1].put()


        else: # Step already contains completion information
            logging.info(f"Run {run_id} already has an 'Run End Time', nothing done.")

    logging.info(f"NovaSeq X run monitoring completed at {datetime.datetime.now()}")


if __name__ == "__main__":
    configure_logging()
    try:
        main()
    except:
        logging.exception("Error in run monitoring")

