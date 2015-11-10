from flask import Flask, render_template, url_for, request, Response, redirect
from genologics.lims import *
from genologics import config
import re
import requests
import datetime
import threading
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

INSTRUMENTS = ["HiSeq", "NextSeq", "MiSeq"]

# With indexes into INSTRUMENTS array
FLOWCELL_INSTRUMENTS = {
	"Illumina Flow Cell": 0,
	"Illumina Rapid Flow Cell": 0,
	"NextSeq Reagent Cartridge": 1, 
	"MiSeq Reagent Cartridge": 2
	}
# List of process types
SEQUENCING = [
        ("Illumina Sequencing (Illumina SBS) 5.0"),
        ("NextSeq Run (NextSeq) 1.0"),
        ("MiSeq Run (MiSeq) 5.0")
        ]

# List of process types
DATA_PROCESSING = [
        ("Demultiplexing and QC NSC 2.0"),
        ("Demultiplexing and QC NSC 2.0"),
        ("Demultiplexing and QC NSC 2.0"),
        ]

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
        ('hiseq', 'Illumina Sequencing (Illumina SBS) 5.0'),
        ('nextseq', 'NextSeq Run (NextSeq) 1.0'),
        ('miseq', 'MiSeq Run (MiSeq) 5.0')
        ]

recent_run_cache = {}
sequencing_process_type = []

def get_sequencing_process(process):
    """As seen in pipeline/common/utilities.py."""
    first_io = process.input_output_maps[0]
    first_in_artifact = first_io[0]['uri']
    processes = process.lims.get_processes(inputartifactlimsid=first_in_artifact.id)
    for proc in processes:
        if proc.type.name in [p[1] for p in SEQ_PROCESSES]:
            return proc


class Project(object):
    def __init__(self, url, name, eval_url):
        self.url = url
        self.eval_url = eval_url
        self.name = name


class SequencingInfo(object):
    def __init__(self, name, url, flowcell_id, projects, status, runid, finished=None):
        self.name = name
        self.url = url
        self.flowcell_id = flowcell_id
        self.projects = projects
        self.status = status
        self.runid = runid
        self.finished = finished


class DataAnalysisInfo(object):
    def __init__(self, name, url, projects, current_job,
            status, seq_url, runid, finished=None):
        self.name = name
        self.url = url
        self.projects = projects
        self.status = status
        self.current_job = current_job
        self.seq_url = seq_url
        self.runid = runid
        self.finished = finished


class CompletedRunInfo(object):
    def __init__(self, url, demultiplexing_url, runid, projects, date):
        self.url = url
        self.demultiplexing_url = demultiplexing_url
        self.runid = runid
        self.projects = projects
        self.date = date


def background_clear_monitor(completed):
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
    eval_url = url_for('go_eval', project_name = lims_project.name)
    return Project(url, lims_project.name, eval_url)


def get_projects(process):
    lims_projects = set(
            art.samples[0].project
            for art in process.all_inputs()
            )
    return [read_project(p) for p in lims_projects]


def estimated_time_completion(process, rapid, done_cycles, total_cycles):
    if total_cycles > 0 and done_cycles < total_cycles:
        now = datetime.datetime.now()
        if rapid:
            time_per_cycle = 430
        else:
            time_per_cycle = 2160
        time_left = seconds=(total_cycles - done_cycles) * time_per_cycle
        est_arrival = now + datetime.timedelta(seconds=time_left)
        return " (ETA: " + est_arrival.strftime("%a %d/%m %H:%M") + ")"
    else:
        return ""



def read_sequencing(process_name, process):
    url = proc_url(process.id)
    flowcell = process.all_inputs()[0].location[0]
    flowcell_id = flowcell.name
    if "NextSeq" in process_name:
        step = Step(lims, id=process.id)
        for lot in step.reagentlots.reagent_lots:
            if lot.reagent_kit.name == "NextSeq 500 FC v1":
                flowcell_id = lot.name
    if "MiSeq" in process_name:
        pass
    lims_projects = set(
            art.samples[0].project
            for art in process.all_inputs()
            )
    projects = get_projects(process)
    try:
        runid = process.udf['Run ID']
    except KeyError:
        runid = ""
    try:
        status = process.udf['Status']
        cycles_re = re.match(r"Cycle (\d+) of (\d+)", status)
        if cycles_re:
            status += estimated_time_completion(
                    process, 
                    "Rapid" in flowcell.type.name,
                    int(cycles_re.group(1)), int(cycles_re.group(2))
                    )

    except KeyError:
        status = "Pending/running"
    try:
        finished = process.udf['Finish Date']
    except KeyError:
        finished = ""

    return SequencingInfo(
            process_name, url, flowcell_id, projects, status, runid, finished
            )

def automation_state(process):
    enabled = any(value for key, value in process.udf.items() if key.startswith("Auto "))
    if enabled:
        state_code = process.udf.get(JOB_STATE_CODE_UDF)
        waiting = not state_code
        completed = False
        if state_code == "COMPLETED":
            checkboxes = sorted(key for key,value in process.udf.items() if key.startswith("Auto "))
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
        status = "Waiting for sequencing"
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


    return DataAnalysisInfo(
            process_name, url, projects, current_job, status, seq_url, runid
            )



def get_recent_run(fc, instrument_index):
    """Get the monitoring page's internal representation of a completed run.
    This will initiate a *lot* of requests, but it's just once per run
    (flowcell).
    
    Caching should be done by the caller."""

    sequencing_process = next(iter(lims.get_processes(
            type=SEQUENCING[instrument_index],
            inputartifactlimsid=fc.placements.values()[0].id
            )))

    url = proc_url(sequencing_process.id)
    try:
        demux_process = next(iter(lims.get_processes(
                type=DATA_PROCESSING[instrument_index],
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
            fc.udf[PROCESSED_DATE_UDF]
            )
    


def get_recently_completed_runs():
    # Look for any flowcells which have a value for this udf
    flowcells = lims.get_containers(
            udf={RECENTLY_COMPLETED_UDF: True},
            type=FLOWCELL_INSTRUMENTS.keys()
            )

    cutoff_date = datetime.date.today() - datetime.timedelta(days=30)
    results = [[],[],[]]
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
            instrument_index = FLOWCELL_INSTRUMENTS[fc.type.name]

            if not run_info:
                # Container types will be cached, so the extra entity request 
                # (for type) is not a problem
                run_info = get_recent_run(fc, instrument_index)
                recent_run_cache[fc.id] = run_info

            results[instrument_index].append(run_info)

        
    return results


def get_batch(instances):
    """Lame replacement for batch call, API only support batch resources for 
    some types of objects.
    
    Note: when / if batch is implemented for these, we'll need to specify 
    force=True for the batch call."""
    for instance in instances:
        instance.get(force=True)

    return instances


@app.route('/')
def get_main():
    global ui_server

    ui_servers = {
            "http://dev-lims.ous.nsc.local:8080/": "https://dev-lims.ous.nsc.local/",
            "http://ous-lims.ous.nsc.local:8080/": "https://ous-lims.ous.nsc.local/",
            "http://cees-lims.sequencing.uio.no:8080/": "https://cees-lims.sequencing.uio.no/"
            }
    ui_server = ui_servers.get(lims.baseuri, lims.baseuri)

    all_process_types = SEQUENCING + DATA_PROCESSING

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
    post_processes = defaultdict(list)
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
                post_processes[p.type.name].append(p)

    clear_task = partial(background_clear_monitor, completed)
    t = threading.Thread(target = clear_task)
    t.run()


    # List of three elements -- Hi,Next,MiSeq, each contains a list of 
    # sequencing processes
    sequencing = [
        [read_sequencing(sp, proc) 
            for proc in seq_processes[sp]]
            for sp in SEQUENCING
        ]


    # List of three sequencer types (containing lists within them)
    post_sequencing = []
    # One workflow for each sequencer type
    for index, step_name in enumerate(DATA_PROCESSING):
        machine_items = [] # all processes for a type of sequencing machine
        for process in post_processes[step_name]:
            sequencing_process = get_sequencing_process(process)
            if sequencing_process and sequencing_process.type.name == SEQUENCING[index]:
                machine_items.append(read_post_sequencing_process(
                    step_name, process, sequencing_process
                    ))
        post_sequencing.append(machine_items)
        

    recently_completed = get_recently_completed_runs()

    body = render_template(
            'processes.xhtml',
            server=lims.baseuri,
            sequencing=sequencing,
            post_sequencing=post_sequencing,
            recently_completed=recently_completed,
            instruments=INSTRUMENTS
            )
    return (body, 200, {'Refresh': '300'})


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

