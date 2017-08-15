from flask import Flask, render_template, url_for, request, Response, redirect, current_app
from genologics.lims import *
from genologics import config
import re
import os
import datetime
import traceback
import threading
import jinja2
from functools import partial
from collections import defaultdict

# Dependencies:
# mod_wsgi yum package
# python-flask yum packages
# python-jinja2

# Project / Sample progress
# ---------------------------------

# Method for generating the progress overview:
# 1. Queues:   No longer supported
# 2. Processes:Process types which should be monitored have a boolean 
#              UDF called "Monitor", with a default of true. This program
#              queries the API for any process of a given type, with the 
#              Monitor flag set. The Monitor flag is cleared if the protocol
#              step is closed in the LIMS.

app = Flask(__name__)

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
page = None

SITE="TESTING"
if SITE == "cees":
    INSTRUMENTS = ["HiSeq 3000/4000", "HiSeq 2500"]

    FLOWCELL_TYPES = set((
            "Illumina Flow Cell",
            "Illumina Rapid Flow Cell",
            ))
    # List of process types
    SEQUENCING = [
            "Illumina Sequencing (HiSeq 3000/4000) 1.0",
            "Illumina Sequencing (Illumina SBS) 5.0",
            ]
else:
    INSTRUMENTS = ["HiSeq X", "HiSeq 3000/4000", "HiSeq 2500", "NextSeq", "MiSeq"]

    FLOWCELL_TYPES = set((
            "Illumina Flow Cell",
            "Illumina Rapid Flow Cell",
            "NextSeq Reagent Cartridge", 
            "MiSeq Reagent Cartridge",
            "Patterned Flow Cell"
            ))
    # List of process types
    SEQUENCING = [
            "Illumina Sequencing (HiSeq X) 1.0",
            "Illumina Sequencing (HiSeq 3000/4000) 1.0",
            "Illumina Sequencing (Illumina SBS) 5.0",
            "NextSeq Run (NextSeq) 1.0",
            "MiSeq Run (MiSeq) 5.0"
            ]

# List of process types
DATA_PROCESSING = "Demultiplexing and QC NSC 2.0"

# Process type for project eval.
PROJECT_EVALUATION = "Project Evaluation Step"

# General, for tracking completed runs
RECENTLY_COMPLETED_UDF = "Recently completed"
PROCESSED_DATE_UDF = "Processing completed date"

# Used by pipeline repo
JOB_STATUS_UDF = "Job status"
JOB_STATE_CODE_UDF = "Job state code"
CURRENT_JOB_UDF = "Current job"
SEQ_PROCESSES=[
        ('hiseqx', 'Illumina Sequencing (HiSeq X) 1.0'),
        ('hiseq4k', 'Illumina Sequencing (HiSeq 3000/4000) 1.0'),
        ('hiseq', 'Illumina Sequencing (Illumina SBS) 5.0'),
        ('nextseq', 'NextSeq Run (NextSeq) 1.0'),
        ('miseq', 'MiSeq Run (MiSeq) 5.0')
        ]

recent_run_cache = {}
sequencing_process_type = []
eval_url_base = ""
template_loc = ""

def get_sequencing_process(process):
    """Gets the sequencing process from a process object corresponing to a process
    which is run after sequencing, such as demultiplexing. This function looks up
    the sequencing step by examining the sibling processes run on one of the
    samples in the process's inputs."""

    # Each entry in input_output_maps is an input/output specification with a single
    # input and any number of outputs. This gets the first input.
    first_io = process.input_output_maps[0]
    first_in_artifact = first_io[0]['uri']

    processes = process.lims.get_processes(inputartifactlimsid=first_in_artifact.id)
    seq_processes = [proc for proc in processes if proc.type.name in [p[1] for p in SEQ_PROCESSES]]
    # Use the last sequencing process. In case of crashed runs, this will be the right one.
    try:
        return seq_processes[-1]
    except IndexError:
        return None

class Project(object):
    def __init__(self, url, name, eval_url):
        self.url = url
        self.eval_url = eval_url
        self.name = name


class SequencingInfo(object):
    def __init__(self, name, url, flowcell_id, projects, status, eta, runid, runtype, finished=None):
        self.name = name
        self.url = url
        self.flowcell_id = flowcell_id
        self.projects = projects
        self.status = status
        self.eta = eta
        self.runid = runid
        self.runtype = runtype
        self.finished = finished


class DataAnalysisInfo(object):
    def __init__(self, name, url, projects, current_job,
            state_code, status, seq_url, runid, finished=None):
        self.name = name
        self.url = url
        self.projects = projects
        self.status = status
        self.state_code = state_code
        self.current_job = current_job
        self.seq_url = seq_url
        self.runid = runid
        self.finished = finished


class CompletedRunInfo(object):
    def __init__(self, url, demultiplexing_url, runid, projects, date, instrument_index):
        self.url = url
        self.demultiplexing_url = demultiplexing_url
        self.runid = runid
        self.projects = projects
        self.date = date
        self.instrument_index = instrument_index


def clear_monitor(completed):
    for proc in completed:
        proc.udf['Monitor'] = False
        proc.put()


def is_step_completed(step):
    """Check if the state of this Step is completed.

    Does not refresh the step, this should be done by a batch request
    prior to calling is_step_completed.
    """
    return step.current_state.upper() == "COMPLETED"


def proc_url(process_id):
    global ui_server
    step = Step(lims, id=process_id)
    state = step.current_state.upper()
    if state == 'COMPLETED':
        page = "work-complete"
    elif state == 'RECORD DETAILS':
        page = "work-details"
    elif state == 'STEP SETUP':
        page = "work-setup"
    else:
        page = "work-details"
    second_part_limsid = re.match(r"[\d]+-([\d]+)$", process_id).group(1)
    return "{0}clarity/{1}/{2}".format(ui_server, page, second_part_limsid)


def read_project(lims_project):
    url = "{0}clarity/search?scope=Project&query={1}".format(ui_server, lims_project.id)
    eval_url = eval_url_base + "?project_name=" + lims_project.name
    return Project(url, lims_project.name, eval_url)


def get_projects(process):
    lims_projects = set(
            art.samples[0].project
            for art in process.all_inputs()
            )
    return [read_project(p) for p in lims_projects if not p is None]


def estimated_time_completion(process, instrument, rapid, dual, done_cycles, total_cycles):
    if total_cycles > 0 and done_cycles < total_cycles:
        now = datetime.datetime.now()
        if instrument == "HiSeq X":
            time_per_cycle = 864 
        elif instrument == "HiSeq 3000/4000":
            time_per_cycle = 755 # Average measured from a 318 cy run
        elif instrument == "HiSeq 2500":
            if done_cycles < 5:
                return "" # Cycle #5 is much longer than others. We can't give a reliable time.
            if rapid:
                time_per_cycle = 430
            elif dual:
                time_per_cycle = 2160
            else:
                time_per_cycle = 1158
        elif instrument == "MiSeq":
            time_per_cycle = 336
        elif instrument == "NextSeq":
            time_per_cycle = 348
        else:
            return ""
        time_left = seconds=(total_cycles - done_cycles) * time_per_cycle
        est_arrival = now + datetime.timedelta(seconds=time_left)
        return est_arrival.strftime("%a %d/%m %H:%M")
    else:
        return ""

def get_run_type(instrument, process):
    if process.udf.get("Status"):
        # HiSeq X / 4000: Not different modes
        #if instrument == "HiSeq X":
        #elif instrument == "HiSeq 3000/4000":
        if instrument == "HiSeq 2500":
            runmode = {
                    "HiSeq Rapid Flow Cell v1": "Rapid",
                    "HiSeq Rapid Flow Cell v2": "Rapid",
                    "HiSeq Flow Cell v4": "High Output v4"
                    }.get(process.udf.get("Flow Cell Version"), "Unknown")
        elif instrument == "NextSeq":
            runmode = process.udf.get("Chemistry", "Unknown")
        elif instrument == "MiSeq":
            container_name = process.all_inputs()[0].location[0].name
            if container_name.endswith("V2"):
                runmode = "MiSeq v2"
            elif container_name.endswith("V3"):
                runmode = "MiSeq v3"
            else:
                runmode = "Unknown"
        else:
            runmode = None

        cycles = "(" + str(process.udf.get("Read 1 Cycles"))
        i1 = process.udf.get("Index 1 Read Cycles")
        if i1:
            cycles += ", " + str(i1)
        i2 = process.udf.get("Index 2 Read Cycles")
        if i2:
            cycles += ", " + str(i2)
        r2 = process.udf.get("Read 2 Cycles")
        if r2:
            cycles += ", " + str(r2)
        cycles += ")"

        if runmode:
            return runmode + " | " + cycles
        else:
            return cycles
    else:
        return ""


def read_sequencing(process_name, process, machines):
    url = proc_url(process.id)
    flowcell = process.all_inputs()[0].location[0]
    flowcell_id = flowcell.name
    instrument = INSTRUMENTS[SEQUENCING.index(process.type.name)]
    run_type = get_run_type(instrument, process)
    lims_projects = set(
            art.samples[0].project
            for art in process.all_inputs()
            )
    projects = get_projects(process)
    eta = None
    machine = None
    try:
        runid = process.udf['Run ID']
        if runid:
            machine = re.match(r"\d{6}_([\dA-Z])+_", runid).group(1)
    except KeyError:
        runid = ""

    other_flowcell_sequencing_info = machines.get(machine)

    try:
        status = process.udf['Status']
        cycles_re = re.match(r"Cycle (\d+) of (\d+)", status)
        if cycles_re:
            if instrument != "MiSeq" or cycles_re.group(1) != "0":
                eta = estimated_time_completion(
                        process, 
                        instrument,
                        "Rapid" in flowcell.type.name,
                        other_flowcell_sequencing_info, #dual flowcell
                        int(cycles_re.group(1)), int(cycles_re.group(2))
                        )
            elif instrument == "MiSeq" and cycles_re.group(1) == "0":
                status = "Cycle <15 of %s" % (cycles_re.group(2))

            if instrument == "HiSeq 2500" and other_flowcell_sequencing_info: # Update for dual
                other_flowcell_sequencing_info.eta = eta

    except KeyError:
        if instrument.startswith("HiSeq"):
            status = "Not yet started"
        else:
            status = "Pending/running"
    try:
        finished = process.udf['Finish Date']
    except KeyError:
        finished = ""

    seq_info = SequencingInfo(
            process_name, url, flowcell_id, projects, status, eta, runid, run_type, finished
            )
    if machine:
        machines[machine] = seq_info
    return seq_info


def automation_state(process):
    enabled = any(value for key, value in process.udf.items() if key.startswith("Auto "))
    if enabled:
        state_code = process.udf.get(JOB_STATE_CODE_UDF)
        waiting = not state_code
        completed = False
        if state_code == "COMPLETED":
            checkboxes = sorted(key for key,value in process.udf.items() if key.startswith("Auto ") and value)
            last_requested_index = int(re.match(r"Auto ([\d]+)", checkboxes[-1]).group(1))
            last_run_index = int(re.match(r"([\d]+).", process.udf[CURRENT_JOB_UDF]).group(1))
            completed = last_run_index >= last_requested_index
        return enabled, waiting, completed
    else:
        return False, False, False

def read_post_sequencing_process(process_name, process, sequencing_process):
    url = proc_url(process.id)
    seq_url = proc_url(sequencing_process.id)
    #flowcell_id = process.all_inputs()[0].location[0].name
    try:
        runid = sequencing_process.udf['Run ID']
    except (KeyError, TypeError):
        runid = ""
        expt_name = ""
    projects = get_projects(process)
    automated, waiting, completed = automation_state(process)

    current_job = ""
    if waiting:
        status = "Waiting for sequencing to complete"
    elif completed:
        status = "All jobs completed"
    else:
        try:
            status = process.udf[JOB_STATUS_UDF]
        except KeyError:
            status = "Open"

        if automated:
            status = "[auto] " + status

        current_job = process.udf.get(CURRENT_JOB_UDF, "")

    state_code = process.udf.get(JOB_STATE_CODE_UDF, "")

    return DataAnalysisInfo(
            process_name, url, projects, current_job, state_code, status, seq_url, runid
            )



def get_recent_run(fc):
    """Get the monitoring page's internal representation of a completed run.
    This will initiate a *lot* of requests, but it's just once per run
    (flowcell).
    
    Caching should be done by the caller."""

    sequencing_process = next(iter(lims.get_processes(
            type=set(SEQUENCING),
            inputartifactlimsid=fc.placements.values()[0].id
            )))

    instrument_index = SEQUENCING.index(sequencing_process.type.name)

    url = proc_url(sequencing_process.id)
    try:
        demux_process = next(iter(lims.get_processes(
                type=DATA_PROCESSING,
                inputartifactlimsid=fc.placements.values()[0].id
                )))
        demultiplexing_url = proc_url(demux_process.id)
    except StopIteration:
        demultiplexing_url = ""

    try:
        runid = sequencing_process.udf['Run ID']
    except KeyError:
        runid = ""
    projects = get_projects(sequencing_process)

    return CompletedRunInfo(
            url,
            demultiplexing_url,
            runid,
            list(projects),
            fc.udf[PROCESSED_DATE_UDF],
            instrument_index
            )
    


def get_recently_completed_runs():
    # Look for any flowcells which have a value for this udf
    flowcells = lims.get_containers(
            udf={RECENTLY_COMPLETED_UDF: True},
            type=FLOWCELL_TYPES
            )

    cutoff_date = datetime.date.today() - datetime.timedelta(days=30)
    results = [list() for i in range(len(SEQUENCING))]
    for fc in reversed(flowcells):
        try:
            date = fc.udf[PROCESSED_DATE_UDF]
        except KeyError:
            fc.get(force=True)
            try:
                date = fc.udf[PROCESSED_DATE_UDF]
            except KeyError:
                date = cutoff_date

        if date <= cutoff_date:
            try:
                del recent_run_cache[fc.id]
            except KeyError:
                pass
            fc.get(force=True)
            fc.udf[RECENTLY_COMPLETED_UDF] = False
            fc.put()
        else:
            run_info = recent_run_cache.get(fc.id)

            if not run_info:
                run_info = get_recent_run(fc)
                recent_run_cache[fc.id] = run_info

            results[run_info.instrument_index].append(run_info)

        
    return results


def get_batch(instances):
    """Lame replacement for batch call, API only support batch resources for 
    some types of objects.
    
    Note: when / if batch is implemented for these, we'll need to specify 
    force=True for the batch call."""
    for instance in instances:
        instance.get(force=True)

    return instances


def prepare_page():
    global page
    global ui_server

    try:
        ui_server = lims.baseuri
        all_process_types = SEQUENCING + [DATA_PROCESSING]

        # Get a list of all processes 
        # Of course it can't be this efficient :( Multiple process types not supported
        #monitored_process_list = lims.get_processes(udf={'Monitor': True}, type=all_process_types)
        monitored_process_list = []
        for ptype in set(all_process_types):
            monitored_process_list += lims.get_processes(udf={'Monitor': True}, type=ptype)

        # Refresh data for all processes (need this for almost all monitored procs, so
        # doing a batch request)
        processes_with_data = get_batch(monitored_process_list)
        # Need Steps to see if COMPLETED, this loads them into cache
        steps = [Step(lims, id=p.id) for p in processes_with_data]
        get_batch(steps)

        seq_processes = defaultdict(list)
        post_processes = []
        completed = []
        for p, step in zip(processes_with_data, steps):
            if p.type.name in SEQUENCING:
                if is_step_completed(step):
                    completed.append(p)
                else:
                    seq_processes[p.type.name].append(p)

            else:
                if is_step_completed(step):
                    completed.append(p)
                else:
                    post_processes.append(p)

        clear_monitor(completed)

        # Keep track of machine-ID, to estimate correct time for single/dual flow cell runs
        machines = {}

        # List of three elements -- Hi,Next,MiSeq, each contains a list of 
        # sequencing processes
        sequencing = [
            [read_sequencing(sp, proc, machines) 
                for proc in seq_processes[sp]]
                for sp in SEQUENCING
            ]


        # List of three sequencer types (containing lists within them)
        post_sequencing = []
        # One workflow for each sequencer type
        for index in range(len(SEQUENCING)):
            machine_items = [] # all processes for a type of sequencing machine
            for process in post_processes:
                sequencing_process = get_sequencing_process(process)
                if sequencing_process and sequencing_process.type.name == SEQUENCING[index]:
                    machine_items.append(read_post_sequencing_process(
                        DATA_PROCESSING, process, sequencing_process
                        ))
            post_sequencing.append(machine_items)
            

        recently_completed = get_recently_completed_runs()

        variables = {
                'updated': datetime.datetime.now(),
                'static': static_url,
                'server': lims.baseuri,
                'sequencing': sequencing,
                'post_sequencing': post_sequencing,
                'recently_completed': recently_completed,
                'instruments': INSTRUMENTS
                }
        page = jinja2.Environment(
                loader=jinja2.FileSystemLoader(template_loc)
                ).get_template('processes.xhtml').render(variables)

    except:
        page = traceback.format_exc()
    threading.Timer(60, prepare_page).start()
    


@app.route('/')
def get_main():
    global page
    global eval_url_base
    global static_url
    global template_loc

    eval_url_base = url_for('go_eval')
    static_url = request.url + "static"
    template_loc = os.path.join(app.root_path, app.template_folder)

    if not request.url.endswith("/"):
        return redirect(request.url + '/')

    if not page:
        prepare_page()
    return (page, 200, {'Refresh': '60'})


@app.route('/go-eval')
def go_eval():
    project_name = request.args.get('project_name')
    processes = lims.get_processes(projectname=project_name, type=PROJECT_EVALUATION)
    if len(processes) > 0:
        process = processes[-1]
        return redirect(proc_url(process.id))
    else:
        return Response("Sorry, project evaluation not found for " + project_name, mimetype="text/plain")

if __name__ == '__main__':
    app.debug=True
    app.run(host="0.0.0.0", port=5001)

