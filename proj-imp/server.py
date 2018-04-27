import datetime
import time
import re
import os
import io
import threading
import json
import Queue as Mod_Queue # Due to name conflict with genologics
from flask import Flask, url_for, abort, jsonify, Response, request,\
        render_template, redirect
from werkzeug.utils import secure_filename

import requests

from genologics.lims import *
from genologics import config

import indexes

# External project creation backend server

# Intentionally uses a lot of the same technology as the
# base counter (in ../base-counter/). Does not use angular 
# though.

# This will be registered as a WSGI application under a path, 
# PATH. It then accepts requests on PATH/CONF_ID/, where 
# CONF_ID is the name of an external project type, represented
# in a JSON file in the config/ directory.

app = Flask(__name__)
lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

# Global dict that maps type name to job object for project type
# (only one project may be created at a time)
project_types = {}
project_types_lock = threading.Lock()

# Return 404 for root path and subpaths not ending with /
@app.route("/")
def get_root(dummy=None):
    return ("Please specify a project")


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
                "config", project_type_safe + ".json")
                ) as f:
            project_data = json.load(f)
            return project_data
    except IOError:
        abort(500, "Error while getting project type data")


@app.route("/<project_type>/")
def get_project_start_page(project_type):
    project_data = get_project_def(project_type)
    project_title = project_data['project_title_prefix'] +\
            "-" + datetime.date.today().isoformat()
    return render_template("index.html", project_title=project_title, **project_data)


@app.route("/<project_type>/submit", methods=["POST"])
def submit_project(project_type):
    """Trigger creation of a project. Instantly returns a
    page showing the status of project creation."""
    project_data = get_project_def(project_type)

    project_title = request.form.get('project_title', '')
    username = request.form.get('username', '')
    password = request.form.get('password', '')
    parameters = dict((k, v) for k, v in request.form.items() if k.startswith("param_"))

    if '' in [username, password, project_title]:
        return render_template("index.html", username=username, password=password,
                project_title=project_title,
                error_message= "Please specify username, password and project title",
                **project_data)

    try:
        f = request.files['sample_file']
        file_data = io.BytesIO()
        f.save(file_data)
        file_name = secure_filename(f.filename)
        if file_name == "":
            raise ValueError("No file provided")
    except (KeyError, ValueError):
        return render_template("index.html", username=username, password=password, 
                project_title=project_title,
                error_message="Sample file upload failed. Make sure sample file is specified.",
                **project_data)

    with project_types_lock:
        project_type_worker = project_types.setdefault(
                    project_type, ProjectTypeWorker(project_data)
                    )
        if not project_type_worker.active:
            try:
                project_type_worker.start_job(username, password, project_title,
                        file_name, file_data.getvalue(), parameters)
            except LimsCredentialsError:
                # Why abort() here, not render_template?: We can't put the
                # file back into the response, so better encourage the user
                # to press back and try again (with the file).
                abort(403, "Incorrect username or password, please go back "
                        "and try again.")
            except Exception as e:
                abort(500, "LIMS seems to be unreachable: {0}".format(e))

    return redirect(url_for('get_project_status', project_type=project_type))


@app.route("/<project_type>/status")
def get_project_status(project_type):
    """Status page"""

    parameters = get_project_def(project_type)
    parameters['evtSourceUrl'] = url_for('get_stream', project_type=project_type)
    return render_template("status.html", **parameters)


@app.route("/<project_type>/stream")
def get_stream(project_type):
    """SSE stream with progress."""
    with project_types_lock:
        try:
            project_type_worker = project_types[project_type]
        except KeyError:
            abort(404, "No such project type")
        if project_type_worker.job is None:
            abort(500, "No import has been started")
    if project_type_worker.job:
        stream = status_stream(project_type_worker.job)
        return Response(stream, mimetype="text/event-stream")
    else:
        abort(404, "No job found for this project type")


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
            "project_title": job.project_title,
            "step_url": job.step_url,
            "task_statuses": task_statuses,
            "running": job.running,
            "error": job.error,
            "completed": job.completed
        })


def status_stream(job):
    if job.completed:
        brief_status = json.dumps({
            "project_title": job.project_title,
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
    def __init__(self, worker, username, project_title, sample_filename,
            sample_file_data, parameters):
        self.worker = worker
        self.project_type = worker.project_type
        self.project_title = project_title
        self.user = lims.get_researchers(username=username)[0]
        self.project_title = project_title
        self.sample_filename = sample_filename
        self.sample_file_data = sample_file_data
        self.parameters = parameters
        self.samples = []
        self.lims_project = None
        self.lims_samples = []
        self.pool = None
        self.lots = None
        self.sequencing_pool = None
        self.step_url = None
        self.queue = Mod_Queue.Queue()
        self.tasks = [
                CheckFields(self),
                ReadSampleFile(self),
                CheckExistingProjects(self),
                CreateProject(self),
                UploadFile(self),
                CreateSamples(self),
                SetIndexes(self),
                AssignWorkflow(self),
                RunPoolingStep(self),
                FindOrCreateLots(self),
                RunDenatureStep(self),
                StartSequencingStep(self)
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


class CheckFields(Task):
    """Check the data entered into the input boxes, and correct/convert some fields in place."""

    NAME = "Check specified parameters"

    def run(self):
        errors = []
        if not re.match(r"[A-Za-z]+-[A-Za-z0-9]+-\d\d\d\d-\d\d-\d\d$", self.job.project_title):
            errors.append("Project name format error -- See exmaple name -- Only A-Z " +
                            "and numbers supported in middle part.")

        for box in [1,2]:
            if not self.job.parameters.get('param_box{0}lot'.format(box)):
                errors.append('Box {0} LOT not specified.'.format(box))
            v = self.job.parameters.get('param_box{0}ref'.format(box))
            if not v:
                errors.append('Box {0} REF not specified.'.format(box))
            elif not v.startswith("RGT"):
                errors.append('Box {0} REF should start with "RGT".'.format(box))
        cart = self.job.parameters.get('param_cart_id')
        if not cart:
            errors.append("Reagent cartridge ID not specified.")
        else:
            self.job.parameters['param_cart_id'] = self.job.parameters['param_cart_id'].replace("+", "-")
            if not re.match(r"MS\d+-\d\d\dV\d", self.job.parameters['param_cart_id']):
                errors.append("Invalid reagent cartridge ID specified, format check failed.")
        if not self.job.parameters.get('param_miseq', '').startswith("M"):
            errors.append("MiSeq Instrument not specified.")
        try:
            self.job.parameters['param_loading'] = float(self.job.parameters.get('param_loading', '').replace(",", "."))
        except ValueError as e:
            errors.append("Loading concentration not specified or invalid: {0}.".format(e))
        try:
            phix = float(self.job.parameters.get('param_phix', '').replace(",", "."))
            if phix < 0: errors.append("PhiX should be non-negative.")
            if phix > 100: errors.append("PhiX should be less or equal to 100 %.")
            self.job.parameters['param_phix'] = phix
        except ValueError as e:
            errors.append("PhiX concentration not specified or invalid: {0}.".format(e))

        if errors:
            raise ValueError(" ".join(errors))
    

class ReadSampleFile(Task):
    """Read the sample file input."""

    NAME = "Read sample file"

    def run(self):
        sample_table = self.job.sample_file_data.decode('utf-8').splitlines()

        if any(l.startswith('[Data]') for l in sample_table) and\
                any(l.startswith('[Header]') for l in sample_table):
            self.parse_sample_sheet_file(sample_table)
        else:
            self.parse_2col_file(sample_table)

        assert len(set(name for name, index in self.job.samples)) == len(self.job.samples), "Non-unique sample name"
        assert len(set(index for name, index in self.job.samples)) == len(self.job.samples), "Non-unique indexes detected"
        assert all(c.isalnum() or c == "-"
                for name, index in self.job.samples
                for c in name), "Invalid characters in name, A-Z, 0-9 and - allowed."
        assert all(c in "ACGT-"
                for name, index in self.job.samples
                for c in index), "Invalid characters in index."


    def parse_2col_file(self, sample_table):
        """Parse a text file with sample name and index"""

        if len(sample_table[0].split(",")) > 1:
            sep = ","
        elif len(sample_table[0].split(";")) > 1:
            sep = ";"
        else:
            raise ValueError("Invalid csv sample file format.")
        cells = [line.split(sep) for line in sample_table]
        if [v.lower() for v in cells[0]] == ["name", "index"]:
            type = 1
        elif [v.lower() for v in cells[0]] == ["name", "index1", "index2"]:
            type = 2
        else:
            raise ValueError("Headers must be Name and Index, or Name, Index1 and Index2.")
        if type == 1:
            self.job.samples = cells[1:]
        else:
            usable_cells = [row for row in cells[1:] if len(row) == 3]
            self.job.samples = [
                    [name, "-".join([index1, index2])]
                    for name, index1, index2 in usable_cells
                    ]


    def parse_sample_sheet_file(self, sample_table):
        """Parse an Illumina MiSeq sample sheet generated with IEM"""

        sample_name_index = None
        sample_index1_index = None
        sample_index2_index = None
        has_index2 = None
        data_section = False
        header_line = True
        sep = None
        self.job.samples = []
        for i, line in enumerate(sample_table):
            if data_section:
                if header_line:
                    if line.count(",") > 0:
                        sep = ","
                    elif line.count(";") > 0:
                        sep = ";"
                    else:
                        raise ValueError("Sample sheet column header in [Data] section not parsable.")
                    header = [h.lower() for h in line.split(sep)]
                    try:
                        sample_name_index = header.index("sample_name")
                        sample_index1_index = header.index("index")
                    except ValueError as e:
                        raise ValueError("Missing required column " + str(e) + " in [Data] section.")
                    try:
                       sample_index2_index = header.index("index2")
                    except ValueError:
                        has_index2 = False
                    header_line = False
                else: # Not header line
                    c = line.split(sep)
                    if not any(c): # Blank line
                        break
                    try:
                        if has_index2 is None:
                            has_index2 = bool(c[sample_index2_index])
                        if not c[sample_name_index]:
                            raise ValueError("Empty sample name on line {0}.".format(i+1))
                        if has_index2:
                            self.job.samples.append((
                                    c[sample_name_index],
                                    c[sample_index1_index] + "-" + c[sample_index2_index]
                                    ))
                        else:
                            self.job.samples.append((
                                    c[sample_name_index],
                                    c[sample_index1_index]
                                    ))
                    except IndexError:
                        raise ValueError("Not enough columns on line {0}.".format(i+1))
            else: # Not data section
                if line.startswith('[Data]'):
                    data_section = True

        if not data_section:
            raise ValueError("Sample sheet is missing the [Data] section.")
        if not self.job.samples:
            raise ValueError("No samples found in sample sheet.")


class CheckExistingProjects(Task):
    """Refuse to create project if one with the same name exists."""

    NAME = "Check for existing project"

    def run(self):
        projects = lims.get_projects(name=self.job.project_title)
        if projects:
            raise ValueError("A project named {0} already exists.".format(
                self.job.project_title))

class CreateProject(Task):
    NAME = "Create project"

    def run(self):
        self.job.lims_project = lims.create_project(
                name=self.job.project_title,
                researcher=self.job.user,
                open_date=datetime.date.today(),
                udf=self.job.project_type['project_fields']
                )
        
class UploadFile(Task):
    NAME = "Upload sample file"

    def run(self):
        # Would use the upstream file API, but it only supports a real on-disk file!
        gls = lims.glsstorage(self.job.lims_project, self.job.sample_filename)
        f_obj = gls.post()
        f_obj.upload(self.job.sample_file_data)

class CreateSamples(Task):
    NAME = "Create samples"

    def run(self):
        for sample in self.job.samples:
            lims_sample = lims.create_sample(sample[0], self.job.lims_project,
                    udf=self.job.project_type['sample_fields'])
            self.job.lims_samples.append(lims_sample)
            
class SetIndexes(Task):
    NAME = "Set indexes"

    def run(self):
        if not ProjectTypeWorker.all_reagent_types:
            ProjectTypeWorker.all_reagent_types = indexes.get_all_reagent_types()
        errors = []
        for category in self.job.project_type['reagent_category']:
            try:
                result = indexes.get_reagents_for_category(ProjectTypeWorker.all_reagent_types,
                        (reversed(s) for s in self.job.samples), category)
                break
            except indexes.ReagentError as e:
                errors.append(str(e))
        else:
            raise RuntimeError("Index error(s): " + " | ".join(errors))

        artifacts = [sample.artifact for sample in self.job.lims_samples]
        lims.get_batch(artifacts)
        for artifact, rgt in zip(artifacts, result):
            artifact.reagent_labels.add(rgt)
        lims.put_batch(artifacts)

class AssignWorkflow(Task):
    NAME = "Assign to workflow"

    def run(self):
        artifacts = [sample.artifact for sample in self.job.lims_samples]
        workflows = lims.get_workflows(name=self.job.project_type['workflow'])
        if not workflows:
            raise ValueError("Specified workflow {0} does not exist.".format(
                self.job.project_type['workflow']))
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
        process = Process(lims, id=step.id)
        process.technician = self.job.user
        process.put()
        while step.current_state.upper() != "COMPLETED":
            if step.current_state == "Assign Next Steps":
                lims.set_default_next_step(step)
            step.advance()
            step.get(force=True)
            self.status = "Completing step (" + str(step.current_state) + ")"
        self.job.pool = next(o['uri'] for i, o in process.input_output_maps if o['output-type'] == 'Analyte')

class FindOrCreateLots(Task):
    NAME = "Find or create reagent lots"
    
    def run(self):
        self.job.lots = []
        expiry_date = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        for i, box in enumerate([1,2]):
            self.status = "Searching for reagent lot {0}...".format(box)
            kitname = self.job.project_type['box{0}_kit_name'.format(box)]
            lotnumber = self.job.parameters['param_box{0}lot'.format(box)]
            ref = self.job.parameters['param_box{0}ref'.format(box)]
            lots = lims.get_reagent_lots(kitname=kitname, number=lotnumber)
            for lot in lots:
                if lot.name.startswith(ref):
                    break
            else: # No lot found
                self.status = "Creating lot {0}...".format(box)
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
        process = Process(lims, id=step.id)
        process.udf['MiSeq instrument'] = self.job.parameters['param_miseq']
        process.udf['Experiment Name'] = self.job.project_title
        process.technician = self.job.user
        process.put()
        have_run_program = False
        timeout = 60
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
                prog = next(prog for prog in step.available_programs if prog.name == "Generate SampleSheet CSV")
                prog.trigger()
                have_run_program = True
                self.status = "Generating sample sheet..."
                continue
            if step.current_state == "Assign Next Steps":
                lims.set_default_next_step(step)
            step.advance()
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

class ProjectTypeWorker(object):

    all_reagent_types = None

    def __init__(self, project_type):
        self.project_type = project_type
        self.job = None
        self.indexes = []
        self.active = False

    def start_job(self, username, password, project_title, sample_filename,
            sample_file_data, parameters):
        """Start an import task with the specified parameters.
        
        This function is not thread safe! Syncrhonization must be handled
        by the caller.
        """
        assert not self.active

        self.check_lims_credentials(username, password)

        self.job = Job(self, username, project_title, sample_filename,
                sample_file_data, parameters)

        thread = threading.Thread(target=self.run_job)
        self.active = True
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


# Start deveopment server if called on the command line
if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", port=5001, threaded=True)

