#!/usr/bin/python

# Run information update script. Reads information which is not 
# available from LIMS. 

import glob
import os
import re
import sys
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

INSTRUMENT_NAME_MAP = {
            'D00132': 'Hilma',

            'NS500336': 'Nemo',
            'NB501273': 'Nelson',

            'M01132': 'Milo',
            'M01334': 'Mina',
            'M02980': 'Mike',

            'J00146': 'Hiawatha',

            'E00401': 'Roxanne',
            'E00396': 'Dexter',
            'E00426': 'Pixie',
            'E00423': 'Box'
            }


PROCESS_TYPES = [
            "Illumina Sequencing (HiSeq X) 1.0",
            "Illumina Sequencing (HiSeq 3000/4000) 1.0",
            "Illumina Sequencing (Illumina SBS) 5.0",
            "NextSeq Run (NextSeq) 1.0",
            "MiSeq Run (MiSeq) 5.0"
        ]


RUN_STORAGES=[
    "/data/runScratch.boston"
    ]

RUN_ID_MATCH = r"\d\d\d\d\d\d_[A-Z0-9\-_]+"


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

def get_qm(dataset):
    """Get QualityMetrics dataframe and suppress output
    while doing it"""
    tmp_out = sys.stdout
    tmp_err = sys.stderr
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")
    qm = dataset.QualityMetrics()
    sys.stdout = tmp_out
    sys.stderr = tmp_err
    return qm

def get_lane_q30(df, lane, cycle_start, cycle_end):
    global qs
    global moo
    moo = df
    qs = df[(df.lane==lane) & (df.cycle >= cycle_start) & (df.cycle < cycle_end)].sum()
    q30 = qs[("q%d" % (q) for q in range(30, 51))].sum()
    qall = qs.sum()
    if qall == 0.0:
        return 0.0
    return q30 * 100.0 / qall

def hiseq_lane_q30(run_dir, dataset, process):
    lanes = process.all_inputs(resolve=True)
    reads = 1 if process.udf.get('Read 2 Cycles') is None else 2
    do_update = True
    for lane in lanes:
        if lane.udf.get('Yield PF (Gb) R%d' % reads) is None:
            do_update = False
    if do_update:
        read_thresholds = [
            (1, 1 + process.udf['Read 1 Cycles'])
            ]
        if reads == 2:
            r2start = sum([1,
                    process.udf['Read 1 Cycles'],
                    process.udf.get('Index 1 Read Cycles', 0),
                    process.udf.get('Index 2 Read Cycles', 0)
                    ])
            read_thresholds.append((r2start, r2start + process.udf['Read 2 Cycles']))
        qm = get_qm(dataset)
        for lane in lanes:
            for read_index, (start_cycle, end_cycle) in zip( (1,2), read_thresholds ):
                lane_number = int(lane.location[1].split(":")[0])
                q30pct = get_lane_q30(qm.df, lane_number, start_cycle, end_cycle)
                lane.udf['%% Bases >=Q30 R%d' % read_index] = q30pct

        lims.put_batch(lanes)

    return do_update

def update_clusters_pf(ds, process, current_cycle):
    try:
        all_df = ds.TileMetrics().df
    except (ValueError, illuminate.exceptions.InteropFileNotFoundError):
        return # No information yet
    df = all_df[all_df.code == 103] # Number of clusters PF
    r1cycles = process.udf['Read 1 Cycles']
    reads = 1
    if current_cycle > r1cycles:
        reads = 2

    lanes = process.all_inputs(resolve=True)
    for lane_ana in lanes:
        lane_str = lane_ana.location[1].split(":")[0]
        if lane_str == "A":
            lane = 1
        else: 
            lane = int(lane_str)
        if len(lanes) > 0:
            clusters = df[df.lane == lane].value.sum()
        else:
            clusters = df.sum()
        for i_read in range(1, reads+1):
            lane_ana.udf['Clusters PF R%d' % i_read] = clusters
    lims.put_batch(lanes)

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
                            if process.udf.get("Status"):
                                set_hiseq_reagents(process)
                            else:
                                handle_now = False
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
                                update_clusters_pf(ds, process, current_cycle)
                                process.get(force=True)
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

def set_hiseq_reagents(process):
    step = Step(lims, id=process.id)
    run_id = process.udf.get('Run ID', 'Unknown')
    kits = step.configuration.required_reagent_kits

    sbs_lots_val = process.udf.get('SBS Kit Lot #', '')
    sbs_lots = [part.strip().upper() for part in sbs_lots_val.split(",")]
    if len(sbs_lots) != 2:
        print "Invalid SBS lots '" + sbs_lots_val + "' for run:", run_id
        return
    set_lots = []
    for kit in kits:
        if kit.name.endswith("SBS Reagents 1/2"):
            rgts = sbs_lots
        elif kit.name.endswith("SBS Reagents 2/2"):
            rgts = reversed(sbs_lots)
        else:
            rgts = [process.udf.get("Flow Cell ID", "UNKNOWN_FLOWCELL")]
        found = False
        for rgt in rgts:
            lots = [lot for lot in lims.get_reagent_lots(kitname=kit.name) if lot.name.startswith(rgt) and lot.status == "ACTIVE"]
            if len(lots) > 1:
                print "Error: Multiple lots match for kit", kit.name, ", ID", rgt, ", run ID", run_id
                return
            elif len(lots) == 1:
                set_lots.append(lots[0])
                found = True
        if not found:
            print "Error: No lots found for kit", kit.name, ", ID", " or ".join(rgts), ", run ID", run_id
            return
    existing_lots = step.reagentlots.reagent_lots
    if len(existing_lots) > 0:
        if set(set_lots) == set(existing_lots):
            print "Info: Lots were already specified for run ID", run_id
        else:
            print "Warning: Existing lots for run ID", run_id, "don't match detected lots"
    else:
        step.reagentlots.set_reagent_lots(set_lots)
        print "Info: Set lots for run", run_id

def set_initial_fields(process, run_dir, run_id):
    process.udf['Operator'] = process.technician.username

    for ide, name in INSTRUMENT_NAME_MAP.items():
        if re.match("\\d{6}_%s_.*" % (ide), run_id):
            process.udf['Instrument Name'] = name
            break
    else:
        print "The run ID", run_id, "did not match any of the known instruments, Instrument Name not set."


    tree = ElementTree()
    if process.type_name.startswith("MiSeq Run"):
        tree.parse(os.path.join(run_dir, "runParameters.xml"))
        process.udf['Chemistry Version'] = tree.find("ReagentKitVersion").text.replace("Version", "")
    elif process.type_name.startswith("Illumina Sequencing (Illumina SBS)"):
        tree.parse(os.path.join(run_dir, "runParameters.xml"))
        rp_run_mode = tree.find("Setup/RunMode").text
        if rp_run_mode == "RapidHighOutput":
            process.udf['Run Mode'] = "High Output"
        elif rp_run_mode == "RapidRun":
            process.udf['Run Mode'] = "Rapid"
    process.put()



if __name__ == "__main__":
    main()

