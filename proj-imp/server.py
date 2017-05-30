import datetime
import re
import os
import io
import threading
import json
from flask import Flask, url_for, abort, jsonify, Response, request,\
        render_template, redirect
from werkzeug.utils import secure_filename

from urlparse import urljoin
import requests

from genologics.lims import *
from genologics import config

import indexes

app = Flask(__name__)
lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

# Global dict mapping type name to job object for project type
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
        with open(os.path.join("config", project_type_safe + ".json")) as f:
            project_data = json.load(f)
            return project_data
    except IOError:
        abort(500, "Error while getting project type data")


@app.route("/<project_type>/")
def get_project_start_page(project_type):
    project_title = project_data['project_title_prefix'] +\
            "-" + datetime.date.today().isoformat()
    return render_template("index.html", project_title=project_title, **get_project_def(project_type))


@app.route("/<project_type>/submit", methods=["POST"])
def submit_project(project_type):
    """Trigger creation of a project. Instantly returns a
    page showing the status of project creation."""
    project_data = get_project_def(project_type)

    project_title = request.form.get('project_title', '')
    username = request.form.get('username', '')
    password = request.form.get('password', '')

    if '' in [username, password, project_title]:
        return render_template("index.html", username=username, password=password,
                project_title=project_title,
                error_message="Please specify username, password and project title",
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
                error_message="Sample file upload failure.",
                **project_data)

    with project_types_lock:
        project_type_worker = project_types.setdefault(project_type, ProjectTypeWorker(project_type))
        if not project_type_worker.active:
            try:
                project_type_worker.start_job(username, password, project_title,
                        file_name, file_data.getvalue())
            except LimsCredentialsError:
                # Why abort() here, not render_template?: We can't put the file back into the response,
                # so better encourage the user to press back and try again (with the file).
                abort(403, "Incorrect username or password, please go back and try again.")

    return redirect(url_for('get_project_status', project_type=project_type))


@app.route("/<project_type>/status")
def get_project_status(project_type):
    """Status page"""
    return render_template("status.html", **get_project_def(project_type))


@app.route("/<project_type>/stream")
def get_status():
    """SSE stream with progress."""
    pass

class LimsCredentialsError(ValueError):
    pass

class Task(object):
    NAME = None

    def __init__(self, job):
        self.running = False
        self.completed = False
        self.status = None
        self.error = False
        self.error_message = None
        self.job = job

    def __call__(self):
        try:
            self.running = True
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


class ReadSampleFile(Task):
    """Refuse to create project if one with the same name exists."""

    NAME = "Read sample file"

    def run(self):
        sample_table = self.job.sample_file_data.decode('utf-8').splitlines()
        if len(sample_table[0].split(",")) > 1:
            sep = ","
        elif len(sample_table[0].split(";")) > 1:
            sep ";"
        else:
            raise ValueError("Invalid csv sample file format.")
        cells = [line.split(sep) for line in sample_table]
        if cells[0] == ["name", "index"]:
            type = 1
        elif cells[0] == ["name", "index1", "index2"]:
            type = 2
        else:
            raise ValueError("Headers must be Name and Index, or Name, Index1 and Index2.")
        if type == 1:
            self.job.samples = cells[1:]
        else:
            self.job.samples = [[name] + "-".join([index1, index2]) for name, index1, index2 in cells]

        assert len(set(name for name, index in self.job.samples)) == len(self.job.samples), "Non-unique sample name"


class CheckExistingProject(Task):
    """Refuse to create project if one with the same name exists."""

    NAME = "Check for existing project"

    def run(self):
        projects = lims.get_projects(name=self.job.project_title)
        if projects:
            raise ValueError("A project named {0} already exists.".format(self.project_title))

class CreateProject(Task):
    NAME = "Create project"

    def run(self):
        user = lims.get_researchers(username=self.job.username)[0]
        job.lims_project = lims.create_project(
                name=job.project_title,
                researcher=user,
                open_date=datetime.date.today(),
                udf=job.project_type['project_fields']
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
        for sample in job.samples:
            lims_sample = lims.create_sample(sample[0], self.job.lims_project,
                    udf=self.job.project_type['sample_fields'])
            self.job.lims_samples.append(lims_sample)
            
class SetIndexes(Task):
    NAME = "Set indexes"

    def run(self):
        if not ProjectTypeWorker.all_reagent_types:
            ProjectTypeWorker.all_reagent_types = indexes.get_all_reagent_types()
        result = indexes.get_reagents_for_category(ProjectTypeWorker.all_reagent_types,
                self.job.samples, self.job.project_type['reagent_category'])
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


class RunPoolingStep(Taks):
    NAME = "Run pooling step"

    def run(self):
        # First, get the pooling step ID and the queue
        stepconf = self.job.lims_workflow.protocols[0].steps[0]
        self.status = "Waiting for samples to appear in queue"
        my_artifacts = [sample.artifact for sample in self.job.lims_samples]
        for attempt in range(10):
            queue = stepconf.queue()
            if set(queue.artifacts) >= set(my_artifacts):
                time.sleep(1)
                queue.get(force=True)
        self.status = "Starting step"
        step = lims.create_step(stepconf, my_artifacts)
        self.status = "Running step"



class Job(object):
    tasks = [
            ReadSampleFile(self),
            CheckExistingProjects(self),
            CreateProject(self),
            UploadFile(self),
            CreateSamples(self),
            SetIndexes(self),
            AssignWorkflow(self),
            RunPoolingStep(self)
        ]

    def __init__(self, worker, username, password, project_title,
            sample_filename, sample_file_data):
        self.worker = worker
        self.project_type = worker.project_type
        self.username = username
        self.project_title = project_title
        self.sample_filename = sample_filename
        self.sample_file_data = sample_file_data
        self.samples = []
        self.lims_project = None
        self.lims_samples = None

    def run(self):
        for task in tasks:
            if not task(self):
                break


class ProjectTypeWorker(object):

    all_reagent_types = None

    def __init__(self, project_type):
        self.project_type = project_type
        self.job = None
        self.indexes = []

    def start_job(self, username, password, project_title, sample_filename, sample_file_data):
        """Start an import task with the specified parameters.
        
        This function is not thread safe! Syncrhonization must be handled by the caller.
        """
        assert not self.active

        uri = urljoin(config.BASEURI, 'api')
        r = requests.get(uri, auth=(username, password))
        if r.status_code not in [403, 200]:
            # Note: 403 is OK! It indicates that we have a valid password, but
            # are a Researcher user and thus not allowed to access the API. 
            # If the password is wrong, we will get a 401.
            raise LimsCredentialsError()

        self.job = Job(self, username, password, project_title, sample_filename,
                sample_file_data)

        thread = threading.Thread(target=self.run_job)
        self.active = True
        thread.start()

    def run_job(self):
        try:
            self.job.run()
        finally:
            self.active = False


# Start deveopment server if called on the command line
if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", port=5001, threaded=True)

