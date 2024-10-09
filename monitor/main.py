# -*- coding: utf-8 -*-

from flask import Flask, render_template, url_for, request, Response, redirect, current_app
from genologics.lims import *
from genologics import config
import re
import os
import sys
import datetime
import traceback
import threading
import jinja2
import json
import time
from functools import partial, lru_cache
from collections import defaultdict

# Dependencies:
# mod_wsgi yum package
# python-flask yum packages
# python-jinja2

# Project / Sample progress
# ---------------------------------

# Method for generating the progress overview:
#    Processes:Process types which should be monitored have a boolean 
#              UDF called "Monitor", with a default of true. This program
#              queries the API for any process of a given type, with the 
#              Monitor flag set. This script clears the Monitor flag if
#              the protocol step is closed in the LIMS.

app = Flask(__name__)

page = None

# Process type for project eval.
PROJECT_EVALUATION = "Project Evaluation Step 1.1"

# General, for tracking completed runs
RECENTLY_COMPLETED_UDF = "Recently completed"
PROCESSED_DATE_UDF = "Processing completed date"

# Used by pipeline repo
JOB_STATUS_UDF = "Job status"
JOB_STATE_CODE_UDF = "Job state code"
CURRENT_JOB_UDF = "Current job"

recent_run_cache = {}
sequencing_process_type = []
eval_url_base = ""
template_loc = ""

# Site variable is updated by deployment script. Currently we have cees and ous.
# The line below must not be changed, not even whitespace / comments.
SITE="TESTING"


# This class represents the configuration for a LIMS server
class LimsServer(object):
    def __init__(self, index, settings):
        self.index = index
        self.INSTRUMENTS = settings['INSTRUMENTS']
        self.FLOWCELL_TYPES = settings['FLOWCELL_TYPES']
        self.SEQUENCING = settings['SEQUENCING']
        self.DATA_PROCESSING = settings['DATA_PROCESSING']
        if settings['CREDENTIALS_FILE']:
            credentials_path = os.path.expanduser(settings['CREDENTIALS_FILE'])
            BASEURI, USERNAME, PASSWORD, VERSION, MAIN_LOG = config.load_config(credentials_path)
            self.lims = Lims(BASEURI, USERNAME, PASSWORD)
        else:
            self.lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

servers = []
# Load dynamic configuration settings from JSON file. This is called at the module level 
# in the very bottom of this file.
def run_init(site):
    global servers
    configpath = os.path.join(
            os.path.dirname(__file__),
            "config",
            "{0}.json".format(site)
            )
    with open(configpath) as f:
        data = json.load(f)
        servers = [LimsServer(i, server) for i, server in enumerate(data['SERVERS'])]

def get_run_id(process):
    try:
        return process.udf['Run ID']
    except KeyError:
        return process.udf.get('RunID', '')

@lru_cache(maxsize=30) # Relevant for monitored processes (open runs)
def get_sequencing_process(server, process):
    """Gets the sequencing process from a process object corresponing to a process
    which is run after sequencing, such as demultiplexing. This function looks up
    the sequencing step by examining the sibling processes run on one of the
    samples in the process's inputs."""

    # Each entry in input_output_maps is an input/output specification with a single
    # input and any number of outputs. This gets the first input.
    first_io = process.input_output_maps[0]
    first_in_artifact_id = first_io[0]['limsid']

    # It seems like the LIMS can return bogus data, so we verify the result, and try multiple times
    for attempt in range(1):
        processes = server.lims.get_processes(inputartifactlimsid=first_in_artifact_id)
        seq_processes = [proc for proc in processes if any(proc.type_name in sq for sq in server.SEQUENCING)]
        if all(first_in_artifact_id in [i['limsid'] for i, o in p.input_output_maps]
                    for p in seq_processes):
            break
        else:
            raise RuntimeError("Invalid data returned from API when finding seq process "
                    "for process {}: artifact {} is not an input of process {}.".format(
                    process.id, first_in_artifact_id, seq_processes[-1].id
            ))
        time.sleep(0.1)
    # Use the last sequencing process. In case of crashed runs, this will be the right one.
    try:
        return seq_processes[-1]
    except IndexError:
        raise ValueError("There is no sequencing process for " + process.id)

class Project(object):
    def __init__(self, url, name, eval_url, info_tags):
        self.url = url
        self.eval_url = eval_url
        self.name = name
        self.info_tags = info_tags


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


def proc_url(process):
    step = Step(process.lims, id=process.id)
    state = step.current_state.upper()
    if state == 'COMPLETED':
        page = "work-complete"
    elif state == 'RECORD DETAILS':
        page = "work-details"
    elif state == 'STEP SETUP':
        page = "work-setup"
    else:
        page = "work-details"
    second_part_limsid = re.match(r"[\d]+-([\d]+)$", process.id).group(1)
    ui_server = process.lims.baseuri
    return "{0}clarity/{1}/{2}".format(ui_server, page, second_part_limsid)


def read_project(server, lims_project):
    ui_server = lims_project.lims.baseuri
    url = "{0}clarity/search?scope=Project&query={1}".format(ui_server, lims_project.id)
    eval_url = eval_url_base + "?project_name=" + lims_project.name + "&server=" + str(server.index)
    project_type_tag = {
            'Sensitive': 'S',
            'Non-Sensitive': 'N',
            'Diagnostics': 'E',
            'Immunology': 'E',
            'Microbiology': 'E',
            'FHI-Covid19': 'C',
            'MIK-Covid19': 'C',
            }
    tag = project_type_tag.get(lims_project.udf.get('Project type'), '?!')
    delivery_method_tag = {
            'User HDD': 'S',
            'New HDD': 'S',
            'TSD project': 'S',
            'NeLS project': 'N',
            'Norstore': 'N',
            'Transfer to diagnostics': '',
            'FHI-Covid19': '',
            'MIK-Covid19': '',
            }
    if tag != "E":
        tag += delivery_method_tag.get(lims_project.udf.get('Delivery method'), '?!')
        if lims_project.udf.get('Bioinformatic services'):
            tag += "B"
    return Project(url, lims_project.name, eval_url, tag)

@lru_cache(maxsize=30*4) # Relevant for all processes x lanes, but "recently completed" is already cached
def get_projects_for_artifacts(server, artifacts):
    return set(
        sample.project
        for art in artifacts
        for sample in server.lims.get_batch(art.samples)
        if sample.project
        )

@lru_cache(maxsize=15) # Cache project lists, because it's prone to getting invalid results
def get_projects(server, process):
    lims_projects = []
    for attempt in range(3): 
        if len(set(i['parent-process'] for i, o in process.input_output_maps)) == 1:
            # Valid single parent process
            break
        else:
            process.get(force=True)
        time.sleep(0.1)
    else: # for..else branch taken if didn't break
        raise RuntimeError("Invalid list of input artifacts to process {}.".format(process.id))
    unique_inputs = frozenset(i['uri'].stateless for i,o in process.input_output_maps)
    lims_projects = get_projects_for_artifacts(server, unique_inputs)
    return [read_project(server, p) for p in lims_projects]


def estimated_time_completion(process, instrument, rapid, done_cycles, total_cycles):
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
            else:
                time_per_cycle = 1158
        elif instrument == "MiSeq":
            if rapid:
                time_per_cycle = 275
            else:
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
            runmode = process.udf.get("Run Mode", "?")
        elif instrument == "NextSeq":
            runmode = process.udf.get("Chemistry", "?")
        elif instrument == "MiSeq":
            try:
                runmode = "MiSeq " + process.udf["Reagent Kit Type"]
            except KeyError:
                runmode = "?"
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


def get_instrument_index_for_processtype(server, processtypename):
    for i, sequencing in enumerate(server.SEQUENCING):
        if processtypename in sequencing:
            return i
    raise ValueError("No such process type: " + str(processtypename))


def read_sequencing(server, process):
    url = proc_url(process)
    flowcell = process.all_inputs()[0].location[0]
    flowcell_id = flowcell.name
    instrument = server.INSTRUMENTS[get_instrument_index_for_processtype(server, process.type_name)]
    run_type = get_run_type(instrument, process)
    projects = get_projects(server, process)
    eta = None
    try:
        runid = get_run_id(process)
    except KeyError:
        runid = ""

    try:
        status = process.udf['Status']
        cycles_re = re.match(r"Cycle (\d+) of (\d+)", status)
        if cycles_re:
            if instrument != "MiSeq" or cycles_re.group(1) != "0":
                eta = estimated_time_completion(
                        process, 
                        instrument,
                        "Rapid" in flowcell.type_name or process.udf.get('Chemistry Version') == "2",
                        int(cycles_re.group(1)), int(cycles_re.group(2))
                        )
            elif instrument == "MiSeq" and cycles_re.group(1) == "0":
                status = "Cycle <26 of %s" % (cycles_re.group(2))

    except KeyError:
        if 'Run Status' in process.udf:
            status = process.udf['Run Status']
        elif instrument.startswith("HiSeq"):
            status = "Not yet started"
        else:
            status = "Pending/running"
    try:
        if process.udf.get("Status") == "Completed":
            finished = "Completed"
        else:
            finished = process.udf['Finish Date']
    except KeyError:
        finished = ""

    seq_info = SequencingInfo(
            process.type_name, url, flowcell_id, projects, status, eta, runid, run_type, finished
            )
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

def read_post_sequencing_process(server, process, sequencing_process):
    url = proc_url(process)
    seq_url = proc_url(sequencing_process)
    #flowcell_id = process.all_inputs()[0].location[0].name
    try:
        runid = get_run_id(sequencing_process)
    except (KeyError, TypeError):
        runid = ""
        expt_name = ""
    projects = get_projects(server, process)
    automated, waiting, completed = automation_state(process)

    current_job = ""
    if waiting:
        status = "Waiting for sequencing to complete"
    elif completed:
        status = "All jobs completed"
    else:
        if JOB_STATUS_UDF in process.udf:
            status = process.udf[JOB_STATUS_UDF]
        else:
            status = process.udf.get('Status', "Open")

        if automated:
            status = "[auto] " + status

        current_job = process.udf.get(CURRENT_JOB_UDF, "")

    state_code = process.udf.get(JOB_STATE_CODE_UDF, "")

    return DataAnalysisInfo(
            process.type_name, url, projects, current_job, state_code, status, seq_url, runid
            )



def get_recent_run(server, fc):
    """Get the monitoring page's internal representation of a completed run.
    This will initiate a *lot* of requests, but it's just once per run
    (flowcell).
    
    Caching should be done by the caller."""

    sequencing_process = next(iter(server.lims.get_processes(
            type=sum(server.SEQUENCING, []),
            inputartifactlimsid=next(iter(fc.placements.values())).id
            )))

    instrument_index = get_instrument_index_for_processtype(server, sequencing_process.type_name)

    url = proc_url(sequencing_process)
    try:
        demux_process = next(iter(fc.lims.get_processes(
                type=server.DATA_PROCESSING,
                inputartifactlimsid=next(iter(fc.placements.values())).id
                )))
        demultiplexing_url = proc_url(demux_process)
    except StopIteration:
        demultiplexing_url = ""

    try:
        runid = get_run_id(sequencing_process)
    except KeyError:
        runid = ""
    projects = get_projects(server, sequencing_process)

    return CompletedRunInfo(
            url,
            demultiplexing_url,
            runid,
            list(projects),
            fc.udf[PROCESSED_DATE_UDF],
            instrument_index
            )
    


def get_recently_completed_runs(servers):
    all_results = []
    for server in servers:
        # Look for any flowcells which have a value for this udf
        flowcells = server.lims.get_containers(
                udf={RECENTLY_COMPLETED_UDF: True},
                type=server.FLOWCELL_TYPES
                )

        cutoff_date = datetime.date.today() - datetime.timedelta(days=30)
        server_results = [list() for i in range(len(server.SEQUENCING))]
        for fc in reversed(flowcells):
            try:
                date = fc.udf[PROCESSED_DATE_UDF]
            except KeyError:
                fc.get(force=True)
                try:
                    date = fc.udf[PROCESSED_DATE_UDF]
                except KeyError:
                    # Set a date (Necessary for SeqLab, can't hook into the Sequence process)
                    fc.udf[PROCESSED_DATE_UDF] = datetime.date.today()
                    fc.put()

            if date <= cutoff_date:
                try:
                    del recent_run_cache[(server, fc.id)]
                except KeyError:
                    pass
                fc.get(force=True)
                fc.udf[RECENTLY_COMPLETED_UDF] = False
                fc.put()
            else:
                run_info = recent_run_cache.get((server, fc.id))
                if not run_info:
                    run_info = get_recent_run(server, fc)
                    recent_run_cache[(server, fc.id)] = run_info

                server_results[run_info.instrument_index].append(run_info)

        all_results += server_results
        
    return all_results


def refresh(instances):
    """Refresh all instances.
    
    This could be replaced by a few batch calls if that becomes available for Process / Step."""
    for instance in instances:
        instance.get(force=True)
    return instances


def prepare_page():
    global page

    try:
        servers_seq_process_types = [
            (server, proctypes) for server in servers for proctypes in server.SEQUENCING]

        servers_data_process_types = [
            (server, [proctype]) for server in servers for proctype in server.DATA_PROCESSING]

        all_servers_process_types = servers_seq_process_types + servers_data_process_types

        # Get a list of all processes 
        # Of course it can't be this efficient :( Multiple process types not supported
        #monitored_process_list = lims.get_processes(udf={'Monitor': True}, type=all_process_types)
        monitored_process_list = []
        for server, ptypes in all_servers_process_types:
            monitored_process_list += [ (server, proc)
                            for ptype in ptypes
                            for proc in server.lims.get_processes(udf={'Monitor': True}, type=ptype)
                            ]

        # Refresh data for all processes (need this for almost all monitored procs, so
        # doing a batch request)
        refresh(proc for server, proc in monitored_process_list)

        # Need Steps to see if COMPLETED, this loads them into cache
        steps = [Step(s.lims, id=p.id) for s, p in monitored_process_list]
        refresh(steps)

        seq_processes = defaultdict(list)
        post_processes = []
        completed = []
        for (server, p), step in zip(monitored_process_list, steps):
            if any(p.type_name in ptypes for ptypes in server.SEQUENCING):
                if is_step_completed(step):
                    completed.append(p)
                else:
                    seq_processes[p.type_name].append(p)

            else:
                if is_step_completed(step):
                    completed.append(p)
                else:
                    post_processes.append((server,p))

        clear_monitor(completed)

        # List of one element per (server, machine type)
        sequencing = [
            [read_sequencing(server, proc) 
                for sp in sptypes
                for proc in seq_processes[sp] ]
                for (server, sptypes) in servers_seq_process_types
            ]


        # This list contains one item for each sequencer type, and each item is a list of processses
        # These are the Demultiplexing and QC processes.
        post_sequencing = []

        # Adding post-sequencing processes to the correct column:
        # One workflow for each sequencer type - loops over all sequencing process type lists, one for each
        # sequencer type and for each server (if applicable).
        for seqtype_server, seq_process_types in servers_seq_process_types:
            # Process this sequencer type, like "MiSeq"
            machine_items = [] # all processes for a type of sequencing machine
            for (server, process) in post_processes:
                # lookup sequencing process
                try:
                    sequencing_process = get_sequencing_process(server, process)
                    if sequencing_process.type_name in seq_process_types:
                        machine_items.append(read_post_sequencing_process(server, process, sequencing_process))
                except ValueError:
                    # Unable to find sequencing process at this time
                    pass
            post_sequencing.append(machine_items) # Add all post-seq for this sequencer type

        recently_completed = get_recently_completed_runs(servers)


        variables = {
                'updated': datetime.datetime.now(),
                'static': 'STATIC_URL_PLACEHOLDER!',
                'sequencing': sequencing,
                'post_sequencing': post_sequencing,
                'recently_completed': recently_completed,
                'instruments': sum((server.INSTRUMENTS for server in servers), [])
                }
        page = jinja2.Environment(
                loader=jinja2.FileSystemLoader(template_loc)
                ).get_template('processes.xhtml').render(variables)

    except:
        page = traceback.format_exc()
    threading.Timer(60, prepare_page).start()
    

def process_type_to_instrument(server, process_type):
    for pt, inst in zip(server.SEQUENCING, server.INSTRUMENTS):
        if process_type == pt:
            return inst
    return "UNKNOWN_INSTRUMENT"


@app.route('/')
def get_main():
    global page
    global eval_url_base
    global template_loc

    eval_url_base = url_for('go_eval')
    # The URL may vary from request to request, so we can't put it in the "page" string. Instead use a
    # placeholder.
    static_url = request.url + "static"
    template_loc = os.path.join(app.root_path, app.template_folder)

    if not request.url.endswith("/"):
        return redirect(request.url + '/')

    if not page:
        prepare_page()
    return (page.replace('STATIC_URL_PLACEHOLDER!', static_url), 200, {'Refresh': '60'})


@app.route('/go-eval')
def go_eval():
    project_name = request.args.get('project_name')
    server = int(request.args.get('server', 0))
    processes = servers[server].lims.get_processes(projectname=project_name, type=PROJECT_EVALUATION)
    if len(processes) > 0:
        process = processes[-1]
        return redirect(proc_url(process))
    else:
        return Response("Sorry, project evaluation not found for " + project_name, mimetype="text/plain")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        SITE = sys.argv[1]
    run_init(SITE)
    app.debug=True
    app.run(host="0.0.0.0", port=5001)
else:
    run_init(SITE)

