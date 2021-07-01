# -*- coding: utf-8 -*-

from flask import Flask, redirect, request, jsonify, Response, send_file
from genologics.lims import *
from genologics import config
import io
import zipfile
import re
import sys
import os
import glob

app = Flask(__name__)

CURRENT_RUN_DIRS = ["/data/runScratch.boston", "/boston/diag/runs"]
CURRENT_RUN_GLOBS = ["{0}/[0-9]*_*_*/".format(crd) for crd in CURRENT_RUN_DIRS]
ARCHIVE_RUN_DIRS = ["/data/runScratch.boston/processed"]
ARCHIVE_RUN_GLOBS = ["{0}/[0-9]*_*_*/".format(ard) for ard in ARCHIVE_RUN_DIRS]


@app.route('/')
def get_main():
    return redirect(request.url.rstrip("/") + '/static/main.html')


@app.route('/runs/<collection>')
def get_runs(collection):
    if collection == "current":
        run_paths = sum((glob.glob(x) for x in CURRENT_RUN_GLOBS), [])
    elif collection == "archive":
        run_paths = sum((glob.glob(x) for x in ARCHIVE_RUN_GLOB), [])
    else:
        return "Error: Invalid collection", 400
    run_ids = [os.path.basename(r.rstrip("/")) for r in run_paths]
    return jsonify(run_ids=sorted(run_ids, reverse=True))


def add_directory(zfile, source_base, dest_base):
    for f in os.listdir(source_base):
        source_path = os.path.join(source_base, f)
        dest_path = os.path.join(dest_base, f)
        if os.path.isdir(source_path):
            add_directory(zfile, source_path, dest_path)
        else:
            zfile.write(source_path, dest_path)


def rangeexpand(txt):
    # https://www.rosettacode.org/wiki/Range_expansion#Python
    lst = []
    for r in txt.split(','):
        if '-' in r[1:]:
            r0, r1 = r[1:].split('-', 1)
            lst += range(int(r[0] + r0), int(r1) + 1)
        else:
            lst.append(int(r))
    return lst


@app.route('/dl/<collection>/<run_id>.zip')
def get_zip_file(collection, run_id):
    try:
        base_dirs = {
                "current": CURRENT_RUN_DIRS,
                "archive": ARCHIVE_RUN_DIRS
                }[collection]
    except KeyError:
        return "Error: Invalid collection specified", 400
    if not re.match(r"[0-9]+_[0-9a-zA-Z-_]+$", run_id):
        return "Error: Invalid run-id specified", 400
    for base_dir in base_dirs:
    	run_path = os.path.join(base_dir, run_id)
        if os.path.isdir(run_path):
            break
    else:
        return "Error: Run doesn't exist", 400
    outputbuffer = io.BytesIO()
    zfile = zipfile.ZipFile(outputbuffer, 'w', allowZip64=True)
    for file in request.args.get('files', '').split(','):
        try:
            if file in ("RunInfo.xml", "RTAConfiguration.xml"):
                zfile.write(
                        os.path.join(base_dir, run_id, file),
                        os.path.join(run_id, file)
                        )
            elif file == "runParameters.xml":
                for file_test in ["runParameters.xml", "RunParameters.xml"]:
                    path = os.path.join(base_dir, run_id, file_test)
                    if os.path.isfile(path):
                        zfile.write(path, os.path.join(run_id, file_test))
            elif file in [
                    "InterOp", "Images", "RTALogs", "Logs", "Recipe", "Config"
                    ]:
                add_directory(
                        zfile,
                        os.path.join(run_path, file),
                        os.path.join(run_id, file)
                        )
            elif file == "Thumbnail_Images":
                cycles = rangeexpand(request.args.get("cycles", "1"))
                lanes = rangeexpand(request.args.get("lanes", "1"))
                for lane in lanes:
                    for cycle in cycles:
                        rel_path = os.path.join(
                                "Thumbnail_Images",
                                "L00{0}".format(lane),
                                "C{0}.1".format(cycle)
                                )
                        source = os.path.join(run_path, rel_path)
                        if os.path.isdir(source):
                            add_directory(
                                    zfile,
                                    source,
                                    os.path.join(run_id, rel_path)
                                    )
        except OSError as e:
            if e.errno == 2:
                pass # Missing file!
            else:
                raise
    zfile.close()
    outputbuffer.seek(0)
    return send_file(outputbuffer, mimetype="application/zip")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        SITE = sys.argv[1]
    app.debug=True
    app.run(host="0.0.0.0", port=5001)

