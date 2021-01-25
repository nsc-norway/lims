import datetime
import time
import re
import os
import io
import threading
import yaml
import json
import Queue as Mod_Queue # Due to name conflict with genologics
from flask import Flask, url_for, abort, jsonify, Response, request,\
        render_template, redirect
from werkzeug.utils import secure_filename

import requests

from genologics.lims import *
from genologics import config

# External project creation backend server

# This will be registered as a WSGI application under a path, 
# PATH.

app = Flask(__name__)
lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

# Global dict that maps type name to job object for project type
# (only one project may be created at a time)
workers = {}
workers_lock = threading.Lock()

# Return 404 for root path and subpaths not ending with /
@app.route("/")
def get_project_start_page():
    return render_template("index.html")


def get_project_def(project_type):
    """Get the project type JSON definition. Calls abort()
    on error, to return HTTP status code.
    
    Returns a dict from deserialized JSON."""
    try:
        project_type_safe = secure_filename(project_type)
        if project_type_safe == "":
            raise ValueError("Invalid project name")
        with open(os.path.join(
                os.path.dirname(__file__),
                "config", project_type_safe + ".yaml")
                ) as f:
            project_data = yaml.safe_load(f)
            return project_data
    except IOError:
        abort(500, "Error while getting project type data")


@app.route("/submit", methods=["POST"])
def submit_project():
    """Trigger creation of a project. Instantly returns a
    page showing the status of project creation."""

    template = request.form.get('template', '')
    username = request.form.get('username', '')
    password = request.form.get('password', '')
    projectname = request.form.get('projectname', '')

    if '' in [username, password, template, projectname]:
        return render_template("index.html", username=username, password=password,
                preset_template=template, projectname=projectname,
                error_message= "Please specify username, password, project name and template.")

    if not projectname.replace("-", "").isalnum():
        return render_template("index.html", username=username, password=password,
                preset_template=template, projectname=projectname,
                error_message= "Project name should only contain alphanumerics and hyphen (-).")

    project_template_data = get_project_def(template)
    
    try:
        f = request.files['sample_file']
        file_data = io.BytesIO()
        f.save(file_data)
        file_name = secure_filename(f.filename)
        if file_name == "":
            raise ValueError("No file provided")
    except (KeyError, ValueError):
        return render_template("index.html", username=username, password=password, 
                preset_template=template, projectname=projectname,
                error_message="Sample file upload failed. Make sure sample file is specified.")

    with workers_lock:
        worker = workers.setdefault(
                    projectname, ProjectWorker(project_template_data)
                    )
        if not worker.active:
            try:
                worker.start_job(username, password, projectname,
                        file_name, file_data.getvalue())
            except LimsCredentialsError:
                # Why abort() here, not render_template?: We can't put the
                # file back into the response, so better encourage the user
                # to press back and try again (with the file).
                abort(403, "Incorrect username or password, please go back "
                        "and try again.")
            except Exception as e:
                abort(500, "LIMS seems to be unreachable, or bug in job creation: {0}".format(e))
        
        # Cleanup old workers
        for w in list(workers):
            if workers[w].rundate and workers[w].rundate < datetime.date.today():
                del workers[w]

    return redirect(url_for('get_project_status', projectname=projectname))


@app.route("/status/<projectname>")
def get_project_status(projectname):
    """Status page"""

    parameters = {'evtSourceUrl': url_for('get_stream', projectname=projectname)}
    return render_template("status.html", **parameters)


@app.route("/stream/<projectname>")
def get_stream(projectname):
    """SSE stream with progress."""
    with workers_lock:
        try:
            worker = workers[projectname]
        except KeyError:
            abort(404, "Project is not being processed")
        if worker.job is None:
            abort(500, "No import has been started")
    if worker.job:
        stream = status_stream(worker.job)
        return Response(stream, mimetype="text/event-stream")
    else:
        abort(404, "No job found for this project")


def status_repr(job):
    task_statuses = [
            {
                "running": task.running,
                "error": task.error,
                "completed": task.completed,
                "status": task.status,
                "name": task.NAME
            } for task in job.tasks
        ]
    return json.dumps({
            "project_title": job.projectname,
            "step_url": job.step_url,
            "task_statuses": task_statuses,
            "running": job.running,
            "error": job.error,
            "completed": job.completed
        })


def status_stream(job):
    if job.completed:
        brief_status = json.dumps({
            "project_title": job.projectname,
            "step_url": job.step_url,
            "task_statuses": [],
            "running": False,
            "error": job.error,
            "completed": job.completed
        })
        yield "event: status\ndata: " + brief_status + "\n\n"
        yield "event: shutdown\ndata: null\n\n"
        return
    else:
        yield "event: status\ndata: " + status_repr(job) + "\n\n"

    while job.queue.get(block=True) == "status":
        try:
            # Discard entries if they pile up here
            # Only latest (current) status is of interest
            while job.queue.get(timeout=0) == "status":
                pass
        except Mod_Queue.Empty:
            yield "event: status\ndata: " + status_repr(job) + "\n\n"
        else: # In case we received anything other than "status"
            yield "event: status\ndata: " + status_repr(job) + "\n\n"
            yield "event: shutdown\ndata: null\n\n"
            break


class LimsCredentialsError(ValueError):
    pass


class Task(object):
    NAME = None

    def __init__(self, job):
        self.running = False
        self.completed = False
        self._status = None
        self.error = False
        self.job = job

    def __call__(self):
        try:
            self.running = True
            self.status = None
            self.run()
        except Exception as e:
            self.running = False
            self.error = True
            self.status = str(e)
            return False
        else:
            self.completed = True
            self.running = False
            self.status = None
            return True

    def run(self):
        pass

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, val):
        self._status = val
        self.job.queue.put("status")


class Job(object):
    def __init__(self, worker, username, projectname, sample_filename,
            sample_file_data):
        self.worker = worker
        self.project_template_data = worker.project_template_data
        self.projectname = projectname
        self.user = lims.get_researchers(username=username)[0]
        self.sample_filename = sample_filename
        self.sample_file_data = sample_file_data
        self.samples = []
        self.lims_project = None
        self.lims_samples = []
        #self.pool = None TODO?
        self.step_url = None
        self.queue = Mod_Queue.Queue()
        self.tasks = [
                ReadSampleFile(self),
                CheckExistingProjects(self),
                CreateProject(self),
                UploadFile(self),
                CreatePlateAndSamples(self),
                AssignWorkflow(self),
                #RunPoolingStep(self),
                #CreateLots(self),
                #RunDenatureStep(self),
                #StartSequencingStep(self)
            ]

    def run(self):
        for task in self.tasks:
            if not task():
                break
        self.queue.put("shutdown")

    @property
    def running(self):
        return any(task.running for task in self.tasks)

    @property
    def error(self):
        return any(task.error for task in self.tasks)

    @property
    def completed(self):
        return all(task.completed for task in self.tasks)

    

class ReadSampleFile(Task):
    """Read the sample file input."""

    NAME = "Read sample file"

    def run(self):
        # Parse the file
        sample_table_data = self.job.sample_file_data.decode('utf-8').splitlines()
        sample_table_rows = self.parse_2col_file(sample_table_data)
        # Convert column IDs
        self.job.samples = []
        for name, pos in sample_table_rows:
            m = re.match(r"([A-H])(\d+)$", pos)
            if m and 1 <= int(m.group(2)) <= 12:
                self.job.samples.append((name, "{}:{}".format(m.group(1), m.group(2))))
            else:
                raise ValueError("Invalid well position '{}'".format(pos))
        # Check it
        if not self.job.samples: raise ValueError("No samples found in sample file. Check the format.")
        if len(set(name for name, _ in self.job.samples)) != len(self.job.samples):
            raise ValueError("Non-unique sample name")
        if len(set(pos for _, pos in self.job.samples)) != len(self.job.samples):
            raise ValueError("Duplicate well position(s) detected")
        if not all(c.isalnum() or c == "-"
                for name, _ in self.job.samples
                for c in name):
            raise ValueError("Invalid characters in sample name, A-Z, 0-9 and - allowed.")
        
    def parse_2col_file(self, sample_table):
        """Parse a text file with sample name and index"""

        if len(sample_table[0].split(",")) > 1:
            sep = ","
        elif len(sample_table[0].split(";")) > 1:
            sep = ";"
        else:
            raise ValueError("Invalid csv sample file format.")

        cells = [line.strip().split(sep) for line in sample_table]
        if [v.lower() for v in cells[0]] == ["name", "pos"]:
            type = 1
        else:
            raise ValueError("Headers must be Name and Index, or Name, Index1 and Index2.")
        
        if type == 1:
            return [c for c in cells[1:] if c and len(c) == 2]


class CheckExistingProjects(Task):
    """Refuse to create project if one with the same name exists."""

    NAME = "Check for existing project"
    def run(self):
        projects = lims.get_projects(name=self.job.projectname)
        if projects:
            raise ValueError("A project named {0} already exists.".format(
                self.job.projectname))


class CreateProject(Task):
    NAME = "Create project"

    def run(self):
        self.job.lims_project = lims.create_project(
                name=self.job.projectname,
                researcher=self.job.user,
                open_date=datetime.date.today(),
                udf=self.job.project_template_data['project_fields']
                )
        

class UploadFile(Task):
    NAME = "Upload sample file"

    def run(self):
        # Would use the upstream file API, but it only supports a real on-disk file!
        gls = lims.glsstorage(self.job.lims_project, self.job.sample_filename)
        f_obj = gls.post()
        f_obj.upload(self.job.sample_file_data)


class CreatePlateAndSamples(Task):
    NAME = "Create plate and samples"

    def run(self):
        plate = lims.create_container(type=lims.get_container_types('96 well plate')[0])
        for sample in self.job.samples:
            lims_sample = lims.create_sample(sample[0], self.job.lims_project,
                    container=plate, well=sample[1],
                    udf=self.job.project_template_data['sample_fields'])
            self.job.lims_samples.append(lims_sample)
            

class AssignWorkflow(Task):
    NAME = "Assign to workflow"

    def run(self):
        artifacts = [sample.artifact for sample in self.job.lims_samples]
        workflows = lims.get_workflows(name=self.job.project_template_data['workflow'])
        if not workflows:
            raise ValueError("Specified workflow {0} does not exist.".format(
                self.job.project_template_data['workflow']))
        self.job.lims_workflow = workflows[0]
        lims.route_artifacts(artifacts, workflow_uri=self.job.lims_workflow.uri)


class RunPoolingStep(Task):
    NAME = "Run pooling step"

    def run(self):
        # First, get the pooling step ID and the queue
        stepconf = self.job.lims_workflow.protocols[0].steps[0]
        self.status = "Waiting for samples to appear in queue..."
        my_artifacts = [sample.artifact for sample in self.job.lims_samples]
        for attempt in range(10):
            queue = stepconf.queue()
            if set(queue.artifacts) >= set(my_artifacts):
                time.sleep(1)
                queue.get(force=True)
        self.status = "Starting step..."
        step = lims.create_step(stepconf, my_artifacts, container_type="Tube")
        self.job.step_url = config.BASEURI.rstrip("/") +\
                "/clarity/work-details/" +\
                step.id.partition('-')[2]
        self.status = "Running step..."
        poolable = step.pools.available_inputs
        step.pools.create_pool(self.job.project_type['pool_name'], poolable)
        while step.current_state.upper() != "COMPLETED":
            if step.current_state == "Assign Next Steps":
                lims.set_default_next_step(step)
            step.advance()
            step.get(force=True)
            self.status = "Completing step (" + str(step.current_state) + ")"
        process = Process(lims, id=step.id)
        process.technician = self.job.user
        process.put()
        self.job.pool = next(o['uri'] for i, o in process.input_output_maps if o['output-type'] == 'Analyte')

class CreateLots(Task):
    NAME = "Create reagent lots"
    
    def run(self):
        self.job.lots = []
        expiry_date = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        for i, box in enumerate([1,2]):
            self.status = "Creating lot {0}...".format(box)
            kitname = self.job.project_type['box{0}_kit_name'.format(box)]
            lotnumber = self.job.parameters['param_box{0}lot'.format(box)]
            ref = self.job.parameters['param_box{0}ref'.format(box)]
            try:
                kit = next(iter(lims.get_reagent_kits(name=kitname)))
            except StopIteration:
                raise RuntimeError("The specified kit type {0} does not exits.".format(kitname))
            lot = lims.create_lot(kit, ref, lotnumber, expiry_date, status='ACTIVE')
            self.job.lots.append(lot)

class RunDenatureStep(Task):
    NAME = "Run denature step"

    def run(self):
        # First, get the pooling step ID and the queue
        stepconf = self.job.lims_workflow.protocols[1].steps[0]
        self.status = "Waiting for pool to appear in queue..."
        queue = stepconf.queue()
        for attempt in range(10):
            if any(a.id == self.job.pool.id for a in queue.artifacts):
                break
            time.sleep(3)
            queue.get(force=True)
        self.status = "Running step and setting parameters..."
        step = lims.create_step(stepconf, [self.job.pool], container_type="MiSeq Reagent Cartridge")
        self.job.step_url = config.BASEURI.rstrip("/") +\
                "/clarity/work-details/" +\
                step.id.partition('-')[2]
        step.reagentlots.set_reagent_lots(self.job.lots)
        container = next(iter(step.placements.selected_containers))
        container.name = self.job.parameters['param_cart_id']
        container.put()
        placement_list = step.placements.get_placement_list()
        placement_list[0][1] = (container, 'A:1')
        step.placements.set_placement_list(placement_list)
        step.placements.post()
        self.job.sequencing_pool = placement_list[0][0]
        self.job.sequencing_pool.udf['Loading Conc. (pM)'] = self.job.parameters['param_loading']
        self.job.sequencing_pool.udf['PhiX %'] = self.job.parameters['param_phix']
        self.job.sequencing_pool.put()
        have_run_program = False
        timeout = 120
        while step.current_state.upper() != "COMPLETED":
            if timeout == 0:
                raise RuntimeError("Timeout while advancing step.")
            if step.program_status:
                step.program_status.get(force=True)
                if step.program_status.status in ["RUNNING", "QUEUED"]:
                    time.sleep(2)
                    timeout -= 1
                    continue
                elif step.program_status.status != "OK":
                    raise RuntimeError("Script failed: {0}".format(step.program_status.message))
            if step.current_state.upper() == "RECORD DETAILS" and not have_run_program:
                self.status = "Generating sample sheet..."
                process = Process(lims, id=step.id)
                process.udf['MiSeq instrument'] = self.job.parameters['param_miseq']
                process.udf['Experiment Name'] = self.job.project_title
                process.udf['Read 1 Cycles'] = self.job.read1_cycles
                if self.job.read2_cycles is not None:
                    process.udf['Read 2 Cycles'] = self.job.read2_cycles
                process.technician = self.job.user
                process.put()
                prog = next(prog for prog in step.available_programs if re.match(r"Generate.*SampleSheet", prog.name, re.IGNORECASE))
                prog.trigger()
                have_run_program = True
                self.status = "Generating sample sheet..."
                continue
            if step.current_state == "Assign Next Steps":
                lims.set_default_next_step(step)
            try:
                step.advance()
            except requests.exceptions.HTTPError: # When running scripts, data could be outdated
                timeout -= 1
            time.sleep(1)
            step.get(force=True)
            self.status = "Completing step (" + str(step.current_state) + ")"

class StartSequencingStep(Task):
    NAME = "Start sequencing step"

    def run(self):
        # First, get the pooling step ID and the queue
        stepconf = self.job.lims_workflow.protocols[1].steps[1]
        self.status = "Waiting for samples to appear in queue..."
        for attempt in range(10):
            queue = stepconf.queue()
            if any(a.id == self.job.sequencing_pool.id for a in queue.artifacts):
                break
            time.sleep(3)
            queue.get(force=True)
        self.status = "Starting step..."
        step = lims.create_step(stepconf, [self.job.sequencing_pool])
        process = Process(lims, id=step.id)
        process.technician = self.job.user
        process.put()
        self.job.step_url = config.BASEURI.rstrip("/") +\
                "/clarity/work-details/" +\
                process.id.partition('-')[2]


class ProjectWorker(object):
    """Worker, manages the trhead. Will run one Job, which is to import one project.
    
    (In version 1 project importer, the worker runs all jobs for a specific project type.)
    """

    def __init__(self, project_template_data):
        self.project_template_data = project_template_data
        self.job = None
        self.active = False

    def start_job(self, username, password, project_title, sample_filename,
            sample_file_data):
        """Start an import task with the specified parameters.
        
        This function is not thread safe! Syncrhonization must be handled
        by the caller.
        """
        assert not self.active

        self.check_lims_credentials(username, password)
        self.job = Job(self, username, project_title, sample_filename,
                sample_file_data)
        thread = threading.Thread(target=self.run_job)
        self.active = True
        self.rundate = None
        thread.start()

    def check_lims_credentials(self, username, password):
        """Check supplied username and password. Throws an
        exception if they are incorrect, or if connection to
        LIMS fails."""

        uri = config.BASEURI.rstrip("/") +  '/api'
        r = requests.get(uri, auth=(username, password))
        if r.status_code not in [403, 200]:
            if r.status_code in [500]:
                raise RuntimeError("Internal server error")
            else:
                # Note: 403 is OK! It indicates that we have a valid password, but
                # are a Researcher user and thus not allowed to access the API. 
                # If the password is wrong, we will get a 401.
                raise LimsCredentialsError()

    def run_job(self):
        try:
            self.job.run()
        finally:
            self.active = False
            self.rundate = datetime.date.today()


# Start deveopment server if called on the command line
if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", port=5001, threaded=True)
