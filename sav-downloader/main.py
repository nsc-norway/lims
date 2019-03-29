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


def add_directory(zfile, source_base, dest_base):
    for f in os.listdir(source_base):
        source_path = os.path.join(source_base, f)
        dest_path = os.path.join(dest_base, f)
        if os.path.isdir(f):
            add_directory(zfile, source_path, dest_path)
        else:
            zfile.write(source_path, dest_path)


@app.route('/dl/<collection>/<run_id>.zip')
def get_zip_file(collection, run_id):
    try:
        base_dir = {"current": CURRENT_RUN_DIR, "archive": ARCHIVE_RUN_DIR}[collection]
    except KeyError:
        return "Error: Invalid collection specified", 400
    if not re.match(r"[0-9]+_[0-9a-zA-Z-_]+$", run_id):
        return "Error: Invalid run-id specified", 400
    run_path = os.path.join(base_dir, run_id)
    outputbuffer = io.BytesIO()
    zfile = zipfile.ZipFile(outputbuffer, 'w')
    for file in request.args.get('files', '').split(','):
        try:
            if file in ("RunInfo.xml", "RTAConfiguration.xml"):
                zfile.write(os.path.join(base_dir, run_id, file), os.path.join(run_id, file))
            elif file == "runParameters.xml":
                for file_test in ["runParameters.xml", "RunParameters.xml"]:
                    path = os.path.join(base_dir, run_id, file_test)
                    if os.path.isfile(path):
                        zfile.write(path, os.path.join(run_id, file_test))
            elif file in ["InterOp", "RTALogs", "Logs", "Recipe", "Config"]:
                add_directory(
                        zfile,
                        os.path.join(run_path, file),
                        os.path.join(run_id, file)
                        )
        except OSError as e:
            if e.errno == 2:
                pass # Missing file!
            else:
                raise
    zfile.close()
    return Response(outputbuffer.getvalue(), mimetype="application/zip")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        SITE = sys.argv[1]
    app.debug=True
    app.run(host="0.0.0.0", port=5001)

