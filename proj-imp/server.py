import datetime
import re
import os
import io
import threading
import json
from flask import Flask, url_for, abort, jsonify, Response, request,\
        render_template, redirect
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Global dict mapping type name to job object for project type
# (only one project may be created at a time)
jobs = {}
jobs_lock = threading.Lock()

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

    with jobs_lock:
        job = jobs.setdefault(project_type, Job(project_type))
        if not job.active:
            job.start(username, password, project_data['project_title'], file_name, file_data.getvalue())
    return redirect(url_for('get_projet_status', project_type=project_type))

@app.route("/<project_type>/status")
def get_project_status(project_type):
    return render_template("status.html", **get_project_data(project_type))

@app.route("/<project_type>/stream")
def get_status():
    """Status page"""
    pass

class Job(object):
    def __init__(self, project_type):
        self.project_type = project_type

    def start(self, username, password, project_title, sample_filename, sample_file_data):
        pass

    def run(self):
        pass

    @property
    def active(self):
        return False
    

# Start deveopment server if called on the command line
if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", port=5001, threaded=True)

