# -*- coding: utf-8 -*-

from flask import Flask, redirect, request, jsonify, Response
from genologics.lims import *
from genologics import config
import io
import zipfile
import re
import sys
import os
import glob

app = Flask(__name__)

CURRENT_RUN_DIR = "/data/runScratch.boston"
CURRENT_RUN_GLOB = "{0}/[0-9]*_*_*/".format(CURRENT_RUN_DIR)
ARCHIVE_RUN_DIR = "/data/runScratch.boston/processed"
ARCHIVE_RUN_GLOB = "{0}/[0-9]*_*_*/".format(ARCHIVE_RUN_DIR)


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
        return "Error: Invalid collection", 400
    run_ids = [os.path.basename(r.rstrip("/")) for r in run_paths]
    return jsonify(run_ids=sorted(run_ids, reverse=True))


@app.route('/dl/<collection>/<run_id>.zip')
def get_zip_file(collection, run_id):
    try:
        base_dir = {"current": CURRENT_RUN_DIR, "archive": ARCHIVE_RUN_DIR}[collection]
    except KeyError:
        return "Error: Invalid collection specified", 400
    if not re.match(r"[0-9]+_[0-9a-zA-Z-_]+$", run_id):
        return "Error: Invalid run-id specified", 400
    run_path = os.path.join(base_dir, run_id)
    zfile = io.BytesIO()
    outputfile = zipfile.ZipFile(zfile, 'w')
    for file in request.args.get('files', '').split(','):
        if file in ("runParameters.xml", "RunInfo.xml", "SampleSheet.csv"):
            outputfile.write(os.path.join(base_dir, run_id, file), os.path.join(run_id, file))
        if file == "InterOp":
            for source in glob.glob(os.path.join(base_dir, run_id, "InterOp", "*.*")):
                outputfile.write(source, os.path.join(run_id, "InterOp", os.path.basename(source)))
    outputfile.close()
    return Response(zfile.getvalue(), mimetype="application/zip")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        SITE = sys.argv[1]
    app.debug=True
    app.run(host="0.0.0.0", port=5001)
else:
    run_init(SITE)

