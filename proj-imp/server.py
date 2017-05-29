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
        project_data['project_title'] = project_data['project_title_prefix'] +\
                "-" + datetime.date.today().isoformat()
        return project_data
    except IOError:
        abort(500, "Error while getting project type data")


@app.route("/<project_type>/")
def get_project_start_page(project_type):
    return render_template("index.html", **get_project_def(project_type))


@app.route("/<project_type>/submit", methods=["POST"])
def submit_project(project_type):
    """Trigger creation of a project. Instantly returns a
    page showing the status of project creation."""
    project_data = get_project_def(project_type)

    project_data['project_title'] = request.form.get('project_title', '')
    username = request.form.get('username', '')
    password = request.form.get('password', '')

    if '' in [username, password, project_data['project_title']]:
        return render_template("index.html", username=username, password=password,
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
                error_message="Sample file upload failure.",
                **project_data)

    with project_types_lock:
        project_type_worker = project_types.setdefault(project_type, ProjectTypeWorker(project_type))
        if not project_type_worker.active:
            try:
                project_type_worker.start_job(username, password, project_data['project_title'],
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
    def __init__(self, name, function):
        self.name = name
        self.function = function
        self.running = False
        self.completed = False
        self.error = False
        self.error_message = None

    def __call__(self):
        try:
            self.running = True
            self.function()
        except Exception as e:
            self.running = False
            self.error = True
            self.error_message = e.message
            return False
        else:
            self.completed = True
            self.running = False
            return True

class Job(object):
    tasks = [
            Task("Check for existing project",  self.check_existing_project),
            Task("Create project",              self.create_project),
        ]

    def __init__(self, username, password, project_title, sample_filename, sample_file_data):
        self.username = username
        self.project_title = project_title
        self.sample_filename = sample_filename
        self.sample_file_data = sample_file_data

    def run(self):
        for task in self.tasks:
            if not task():
                break

    def check_existing_project(self):
        projects = lims.get_projects(name=self.project_title)
        if projects:
            raise ValueError("A project named {0} already exists.".format(self.project_title))

    def create_project(self):
        users = lims.get_researchers(username=lims.username)


class ProjectTypeWorker(object):
    def __init__(self, project_type):
        self.project_type = project_type
        self.job = None

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

        self.job = Job(project_type, username, password, project_title, sample_filename,
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

