#!/usr/bin/python

# Run information update script. Reads information which is not 
# available from LIMS. (Note: not processing NovaSeq)

import glob
import os
import re
import sys
import yaml
import datetime
from xml.etree.ElementTree import ElementTree
import xml.parsers.expat
# MatPlotLib, required for use of Pandas DataFrame
os.environ['MPLCONFIGDIR'] = os.path.expanduser("~")
import illuminate
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

DB_FILE = "/var/db/rundb/runs.db"

# RUN DATABASE FORMAT SPEC:

# Run database is only used to track new / running / completed runs,
# to limit the load on LIMS.

# Tab delimited columns:
# RUN_ID    STATUS  LIMSID  CYCLE

# Column STATUS gives one of the values
# NEW, LIMS, COMPLETED
#-
# NEW means that no information was found in LIMS. Will check again on next script execution.
# LIMS means that the run is associated with a LIMS process. Will update the status in LIMS each time.
# COMPLETED means that the run has completed, LIMS status no longer relevant. Run is ignored, removed 
#  from DB once removed from the filesystem.

INSTRUMENT_NAME_MAP = {seq['id']: seq['name']
            for seq in yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "sequencers.yaml")))
            }

PROCESS_TYPES = [
            "Illumina Sequencing (HiSeq X) 1.0",
            "Illumina Sequencing (HiSeq 3000/4000) 1.0",
            "NextSeq 500/550 Run NSC 3.0",
            "MiSeq Run (MiSeq) NSC 5.1"
        ]


RUN_STORAGES=[
    "/data/runScratch.boston",
    "/boston/diag/runs"
    ]

# This RUN ID match string does intentionally not match NovaSeq, which is 111111_A0....
# We don't need this script for NovaSeq, and then we can sidestep the issue that
# the illuminate library doesn't work well with NovaSeq InterOp files.
RUN_ID_MATCH = r"\d\d\d\d\d\d_[B-Z0-9\-_]+"


def get_mi_nextseq_container(run_dir):
    tree = ElementTree()
    recipes = glob.glob(os.path.join(run_dir, "Recipe", "[NM]S*-*.xml"))
    if recipes: # NextSeq / Completed MiSeq
        return re.match(r"(.*)\.xml$", os.path.basename(recipes[0])).group(1)
    try:
        tree.parse(os.path.join(run_dir, "runParameters.xml")) # MiSeq
        return tree.find("ReagentKitRFIDTag/SerialNumber").text
    except xml.parsers.expat.ExpatError:
        pass # This happens

def get_hiseq_container(run_dir):
    tree = ElementTree()
    tree.parse(os.path.join(run_dir, "RunInfo.xml")) # HiSeq
    return tree.find("Run/Flowcell").text

def get_lims_container_name(run_dir):
    """Get the expected LIMS container name.
    
    MiSeq: Reagent cartridge ID
    NextSeq Reagent cartridge ID
    HiSeq: Flowcell ID
    """
    try:
        return get_mi_nextseq_container(run_dir)
    except (IOError, AttributeError):
        return get_hiseq_container(run_dir)


def get_cycle(dataset, run_dir, lower_bound_cycle):
    """Get total cycles and current cycle based on files written in the run folder. 

    Will look at lane 1 only, to reduce I/O and complexity.
    """
    total_cycles = sum(r['cycles'] for r in dataset.Metadata().read_config)
    
    lower_bound_cycle = max(0, lower_bound_cycle)
    for cycle in range(lower_bound_cycle, total_cycles):
        test_paths = [
                os.path.join(
                    run_dir, "Data", "Intensities", "BaseCalls", "L001",
                    "C{0}.1".format(cycle+1)
                ),
                os.path.join(
                    run_dir, "Data", "Intensities", "BaseCalls", "L001",
                    "{0:04d}.bcl.bgzf".format(cycle+1)
                )
            ]
        if not any(os.path.exists(test_path) for test_path in test_paths):
            return cycle, total_cycles

    return total_cycles, total_cycles


def set_run_metadata(ds, run_dir, process):
    process.udf['Run ID'] = ds.meta.runID
    i_data_read = 1
    i_index_read = 1
    for read in sorted(ds.meta.read_config, key=lambda r: r['read_num']):
        if read['is_index']:
            process.udf['Index %d Read Cycles' % (i_index_read)] = read['cycles']
            i_index_read += 1
        else:
            process.udf['Read %d Cycles' % (i_data_read)] = read['cycles']
            i_data_read += 1


def main():
    try:
        with open(DB_FILE) as run_db_file:
            run_db = [l.split("\t") for l in run_db_file.readlines()]
    except IOError:
        run_db = []

    new_runs = set(r[0] for r in run_db if r[1].strip() == "NEW")
    completed_runs = set(r[0] for r in run_db if r[1].strip() == "COMPLETED")
    lims_runs_id_cycle = dict((r[0], [r[2], int(r[3])]) for r in run_db if r[1].strip() == "LIMS")

    # Checks if any runs are missing
    missing_runs = set(completed_runs) | set(lims_runs_id_cycle.keys()) | set(new_runs)

    run_dirs = [r
            for directory in RUN_STORAGES
            for r in glob.glob(os.path.join(directory, "*_*_*"))
            ] 

    for r in run_dirs:
        run_id = os.path.basename(r)

        if not re.match(RUN_ID_MATCH, run_id):
            continue

        missing_runs.discard(run_id)

        if not (run_id in new_runs or lims_runs_id_cycle.has_key(run_id) or run_id in completed_runs):
            if os.path.isdir(r) and\
                            (os.path.isdir(os.path.join(r, "InterOp")) or 
                            os.path.isdir(os.path.join(r, "Recipe"))):
                new_runs.add(run_id)

        if run_id in new_runs:
            # Try to convert it into LIMS state by looking up the flow cell in LIMS
            container_name = get_lims_container_name(r)
            lims_containers = lims.get_containers(name=container_name)
            if lims_containers:
                analyte = lims_containers[-1].placements.values()[0]
                processes = lims.get_processes(inputartifactlimsid=[analyte.id], type=PROCESS_TYPES)
                if processes:
                    process = processes[-1]
                    if set(process.all_inputs()) == set(lims_containers[-1].placements.values()):
                        handle_now = True
                        if "Illumina" in process.type_name: # HiSeq
                            handle_now = process.udf.get("Status")
                        if handle_now:
                            new_runs.remove(run_id)
                            set_initial_fields(process, r, run_id)
                            lims_runs_id_cycle[run_id] = [process.id, -1] # Trigger update 

        if run_id not in completed_runs:
            if os.path.exists(os.path.join(r, "RTAComplete.txt")):
                try:
                    # Remove if in new runs. If already found in LIMS, 
                    # will update one last time with cycle
                    new_runs.remove(run_id)
                    completed_runs.add(run_id)
                except KeyError:
                    pass

    # Update LIMS state runs
    # Batch request for process objects not supported
    ## lims.get_batch([Process(lims, id=id) for (id, cycles) in lims_runs_id_cycle.values()])
    for r in run_dirs:
        run_id = os.path.basename(r)
        if lims_runs_id_cycle.has_key(run_id):
            process_id, old_cycle = lims_runs_id_cycle[run_id]
            process = Process(lims, id=process_id)

            # Completed run
            if process.udf.get('Finish Date'):
                completed_runs.add(run_id)
                del lims_runs_id_cycle[run_id]
                set_final_fields(process, r, run_id)
            else:
                miseq_or_nextseq = re.match(r"\d\d\d\d\d\d_(N|M)[A-Z0-9\-_]+", run_id)
                if miseq_or_nextseq:
                    if "_N" in run_id and not os.path.isdir(os.path.join(r, "InterOp")):
                        if not process.udf.get('Finish Date') and not process.udf.get('Status'):
                            process.udf['Status'] = "Cluster generation"
                            process.udf['Run ID'] = run_id
                            process.put()
                    else:
                        ds = illuminate.InteropDataset(r)
                        current_cycle, total_cycles = get_cycle(ds, r, old_cycle)
                        lims_runs_id_cycle[run_id][1] = current_cycle
                        if current_cycle is not None:
                            if current_cycle != total_cycles:
                                # Update all except last cycle for NextSeq (avoid race with clarity 
                                # integrations for last cycle)
                                if old_cycle == -1:
                                    process.get()
                                    set_run_metadata(ds, r, process)
                                    process.put()
                                else:
                                    process.get(force=True)
                                if 'Run ID'  in process.udf: # Glitches happen. If no UDFs, don't push new changes
                                    process.udf['Status'] = "Cycle %d of %d" % (current_cycle, total_cycles)
                                    if not process.udf.get('Finish Date'): # Another work-around for race condition
                                        process.put()

    completed_runs -= missing_runs
    new_runs -= missing_runs
    for r in missing_runs:
        lims_runs_id_cycle.pop(r, None)

    with open(DB_FILE, "w") as f:
        for r in new_runs:
            f.write("{0}\tNEW\n".format(r))
        for (r, (limsid, c)) in lims_runs_id_cycle.items():
            f.write("{0}\tLIMS\t{1}\t{2}\n".format(r, limsid, c))
        for r in completed_runs:
            f.write("{0}\tCOMPLETED\n".format(r))

def set_initial_fields(process, run_dir, run_id):
    process.udf['Operator'] = process.technician.username

    for ide, name in INSTRUMENT_NAME_MAP.items():
        if re.match("\\d{6}_%s_.*" % (ide), run_id):
            process.udf['Instrument Name'] = name
            break
    else:
        print "The run ID", run_id, "did not match any of the known instruments, Instrument Name not set."

    if process.type_name.startswith("MiSeq Run"):
        rp_tree = ElementTree()
        rp_tree.parse(os.path.join(run_dir, "runParameters.xml"))
        process.udf['Chemistry Version'] = rp_tree.find("ReagentKitVersion").text.replace("Version", "")
        ri_tree = ElementTree()
        ri_tree.parse(os.path.join(run_dir, "RunInfo.xml"))
        num_tiles = ri_tree.find("Run/FlowcellLayout").attrib['TileCount']
        if num_tiles == "4": typ = "v2 Micro"
        elif num_tiles == "2": typ = "v2 Nano"
        elif num_tiles == "14": typ = "v2"
        elif num_tiles == "19": typ = "v3"
        else: typ = "Unknown ({})".format(num_tiles)
        process.udf['Reagent Kit Type'] = typ
    process.udf['Run started'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    process.put()


def set_final_fields(process, run_dir, run_id):
    if process.udf.get('Run finished') is None:
        process.udf['Run finished'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        process.put()

if __name__ == "__main__":
    main()

