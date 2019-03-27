# -*- coding: utf-8 -*-

from flask import Flask, redirect, request, jsonify
from genologics.lims import *
from genologics import config
import re
import sys
import os
import glob

app = Flask(__name__)

param_options_default_on = [
        ("runParameters.xml", lambda par: ["runParameters.xml", "RunParameters.xml"], True),
        ("runParameters.xml", ["runParameters.xml", "RunParameters.xml"], True),
        ("runParameters.xml", lambda par: ["runParameters.xml", "RunParameters.xml"], True),
        ("runParameters.xml", ["runParameters.xml", "RunParameters.xml"], True),
    ]

CURRENT_RUN_GLOB = "/data/runScratch.boston/[0-9]*_*_*/"
ARCHIVE_RUN_GLOB = "/data/runScratch.boston/processed/[0-9]*_*_*/"

@app.route('/')
def get_main():
    return redirect(request.url.rstrip("/") + '/static/main.html')

@app.route('/runs/<collection>')
def get_runs(collection):
    if collection == "current":
        run_paths = glob.glob(CURRENT_RUN_GLOB)
    elif collection == "archive":
        run_paths = glob.glob(ARCHIVE_RUN_GLOB)
    else:
        return "invalid collection", 400
    run_ids = [os.path.basename(r.rstrip("/")) for r in run_paths]
    return jsonify(run_ids=sorted(run_ids))

@app.route('/dl/<collection>/<run_id>.zip')
def get_zip_file():
    return "YO"


if __name__ == '__main__':
    if len(sys.argv) > 1:
        SITE = sys.argv[1]
    app.debug=True
    app.run(host="0.0.0.0", port=5001)
else:
    run_init(SITE)

