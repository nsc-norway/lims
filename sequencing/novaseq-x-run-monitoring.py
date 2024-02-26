#!/usr/bin/python

# Run information update script for NovaSeq X.

# Compared to update-runs.py, it uses a simplistic approach of only relying on LIMS
# to track the run status, no database file used for performance.

import glob
import os
import re
import yaml
import math
import logging
import datetime
import requests
from xml.etree.ElementTree import ElementTree
from interop import py_interop_run_metrics, py_interop_run, py_interop_summary
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

# Load instrument names from config file
INSTRUMENT_NAME_MAP = {seq['id']: seq['name']
            for seq in yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "sequencers.yaml")))
            }

# This script can only handle a single process type and workflow at a time. If there is a
# new version, the script should be updated at the time when the new version is activated.
PROCESS_TYPE_NAME = "AUTOMATED - NovaSeq X Run AMG 1.0"
WORKFLOW_NAME = "NovaSeq X AMG 1.0"

RUN_STORAGES=[
    "/data/runScratch.boston/NovaSeqX"
    ]


RUN_ID_MATCH = r"\d\d\d\d\d\d_[Q0-9\-_]+"

# The values should correspond to reagent kits in Clarity.
REAGENT_TYPES = { #TODO check these
    'Reagent':  'NovaSeq X Reagent',
    'FlowCell': 'NovaSeq X Flow Cell',
    'Buffer':   'NovaSeq X Buffer Cartridge',
    'Lyo':      'NovaSeq X Lyo',
}

def get_library_tube_strip_id(run_parameters_xml):
    """Get the library tube strip ID from the RunParameters.xml file,
    used for matching the container in LIMS. The argument should contain
    an ElementTree object with the parsed XML.
    
    Returns the library tube strip ID, or None if not found."""

    consumable_infos = run_parameters_xml.findall("RunParameters/ConsumableInfo/ConsumableInfo")
    for consumable_info in consumable_infos:
        try:
            if consumable_info.find("ConsumableType").text == "SampleTube":
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
            return stepconf.queue()


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
            return cycle, total_cycles

    # All cycles are complete
    return total_cycles, total_cycles


def set_initial_fields(process, run_parameters, run_id):
    """Set fields that are available immediately when RunParameters.xml is available.
    """

    for ide, name in INSTRUMENT_NAME_MAP.items():
        if re.match("\\d{6}_%s_.*" % (ide), run_id):
            process.udf['Instrument Name'] = name
            break
    else:
        logging.warn("The run ID", run_id, "did not match any of the known instruments, "
                     " 'Instrument Name' not set.")
    
    # Set read lengths
    total_cycles = 0
    try:
        for read in run_parameters.findall("RunParameters/PlannedReads/Read"):
            read_name = read.attrib['Name']
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
    process.udf['Status'] = f"Cycle 0 of {total_cycles}"

    # Set standard metadata
    process.udf['Run started'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    process.udf['Run ID'] = run_id
    if not 'Demultiplexing Process ID' in process.udf:
        process.udf['Demultiplexing Process ID'] = ""
    process.udf['Monitor'] = True # Flag for overview page

    # Set run parameters
    #TODO set same parameters as on NovaSeq 6000

    process.put()


def set_if_not_nan(artifact, field, value):
    if not math.isnan(value):
        artifact.udf[field] = value


def set_lane_qc(process, run_dir):
    # Get the input-output mappings to find the output artifact for each lane
    lane_artifacts = [] # List of (lane, artifact)
    for i, o in process.input_output_maps:
        if o['output-generation-type'] == 'PerInput':
            try:
                lane_number = "ABCDEFGH".index(i['uri'].location[1][0]) + 1
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
        lane_index = lane_number - 1
        nonindex_read_count = 0
        for read in range(read_count):
            read_data = summary.at(read)
            if not read_data.read().is_index():
                read_label = str(nonindex_read_count + 1)
                lane_summary = read_data.at(lane_index)
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
                set_if_not_nan(artifact, f'% Occupied Wells', lane_summary.percent_occupied().mean())
                nonindex_read_count += 1
    lims.put_batch([a for _, a in lane_artifacts])


def create_reagent_lots(run_parameters, run_id):
    """Reagent information is imported into Clarity as reagent lots. This function
    reads the ConsumableInfo section of the RunParameters.xml file and creates
    reagent lots in Clarity for each reagent used in the run.

    TODO determine reagent name in Clarity

    Returns the lot objects.
    """
    lots = []
    for consumable_info in run_parameters.findall("RunParameters/ConsumableInfo/ConsumableInfo"):
        try:
            serial_number = consumable_info.find("SerialNumber").text
            lot_number = consumable_info.find("LotNumber").text
            expiration_date = consumable_info.find("ExpirationDate").text
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
                                             "with serial number {serial_number}.")
                            lot = lims.create_lot(reagent_kits[0], serial_number, lot_number, 
                                                expiration_date, notes=note, status='ACTIVE')
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
    if process.udf.get('Run finished') is None:
        process.udf['Run finished'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        process.put()


def main():
    logging.basicConfig(filename="run_monitoring.log", level=logging.DEBUG)
    
    logging.info(f"Executing NovaSeq X run monitoring at {datetime.datetime.now()}")

    run_dirs = [r
            for directory in RUN_STORAGES
            for r in glob.glob(os.path.join(directory, "*_*_*"))
            if re.match(RUN_ID_MATCH, os.path.basename(r))
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
            logging.warning(f"Run {run_id} does not have a RunParameters.xml file, skipping.")
            continue
        
        library_tube_strip_id = get_library_tube_strip_id(rp_tree)
        if library_tube_strip_id is None:
            logging.warning(f"Run {run_id} does not have a library tube strip ID, skipping.")
            continue

        # Check that the Run ID in the xml file and the run folder name match
        rp_run_id = rp_tree.find("RunParameters/RunId").text
        if rp_run_id != run_id:
            logging.error(f"Run ID in RunParameters.xml {rp_run_id} does not match the run "
                          "folder name {run_id}.")
            continue

        lims_containers = lims.get_containers(name=library_tube_strip_id)
        if not lims_containers:
            logging.warning(f"Run {run_id} does not have a matching container in LIMS, skipping.")
            continue
        
        # Get one of the artifacts in the container
        analyte = lims_containers[-1].placements.values()[0]
        # Look for run processes in LIMS
        processes = lims.get_processes(inputartifactlimsid=[analyte.id], type=PROCESS_TYPE_NAME)

        # Get the process, or start a new one if not available. These branches should both set
        # the process and the step variables.
        if processes:
            process = processes[-1]
            step = Step(lims, id=process.id)
            logging.info(f"Found {len(processes)} processes for run {run_id} in LIMS. Will use "
                            "process {process.id}.")
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

            logging.info(f"Creating and setting reagent lots for run {run_id}.")
            lots = create_reagent_lots(run_dir)
            logging.info(f"Setting used lots on the step.")
            step.reagentlots.set_reagent_lots(lots)

        # We now have a run folder and a matching Process in LIMS. We get the run status
        # from the run folder.
        
        # TODO check flag files
        if not rta_complete:
            logging.info(f"Run {run_id} is not complete, updating progress.")
            cycle_match = re.match(r"Cycle (\d+) of (\d+)", process.udf.get('Status', ''))
            if cycle_match:
                old_cycle = int(cycle_match.group(1))
                total_cycles = int(cycle_match.group(2))
                current_cycle, total_cycles = get_cycle(total_cycles, run_dir, old_cycle)
                if current_cycle != old_cycle:
                    process.udf['Status'] = f"Cycle {current_cycle} of {total_cycles}"
                    process.put()
            else:
                logging.warning(f"Run {run_id} cycle cannot be updated because the status field "
                                "is not in the expected format.")
            
        else: # Sequencing is completed
            logging.info(f"Run {run_id} sequencing is completed.")
            # Get lane QC metrics if we have not already done so
            if process.udf.get('Run finished') is None:
                logging.info(f"Run {run_id} sequencing is completed, updating QC metrics and final fields.")
                set_lane_qc(process, run_dir)
                set_final_fields(process, run_dir, run_id)

            # TODO - demultiplexing step?

    logging.info(f"NovaSeq X run monitoring completed at {datetime.datetime.now()}")


if __name__ == "__main__":
    main()

