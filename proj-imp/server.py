#!/usr/bin/python

import datetime
import re
import threading
import json
from flask import Flask, url_for, abort, jsonify, Response, request,\
        render_template

app = Flask(__name__)

# Global dict mapping type name to project type
# (only one project may be created at a time)
jobs = {}
jobs_lock = threading.Lock()

# Return 404 for root path and subpaths not ending with /
@app.route("/")
@app.route("/<dummy>")
def get_root(dummy=None):
    return ("Please specify a project")


def get_project_def(project_name):
    """Get the project type JSON definition. Calls abort()
    on error, to return HTTP status code.
    
    Returns a dict from deserialized JSON."""
    try:
        if any(not c.isalnum() for c in project_name):
            raise ValueError("Invalid project name")
        with os.path.join("config", project_name + ".json") as f:
            project_data = json.decode(f)
        project_data['project_title'] = project_data['project_title_prefix'] +\
                "-" + datetime.date.today().isoformat()
        return project_data
    except Exception:
        abort(500, "Error while getting project type data")


@app.route("/<project_type>/")
def get_project_start_page(project_type):
    return render_template("index.html", **get_project_def(project))

@app.route("/<project_type>/submit", methods=["POST"])
def submit_project(project_type):
    """Trigger creation of a project. Instantly returns a
    page showing the status of project creation."""

    project_data = get_project_def(project_type)
    with jobs_lock:
        job = jobs.setdefault(project_type, Job())
        if not job.active:
            job.spawn_worker( project_type)

    return render_template("xxx.html", **project_data)


@app.route("/<project_type>/status")
def get_status():
    """SSE stream for processing status"""
    pass

if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", port=5001, threaded=True)

