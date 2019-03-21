# -*- coding: utf-8 -*-

from flask import Flask, render_template, url_for, request, Response, redirect, current_app
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


@app.route('/')
def get_main():
    return redirect(request.url + '/static/main.html')

    run_paths = glob.glob("/data/runScratch.boston/[0-9]*_*_*/")
    run_ids = [os.path.basename(r) for r in run_paths]
    if not request.url.endswith("/"):
    return render_template("main.xhtml", param_options=param_options, run_ids=run_ids)

@app.route('/runs')
def get_runs(old_runs=False):
    pass

@app.route('/zip')
def get_zip_file():
    pass


if __name__ == '__main__':
    if len(sys.argv) > 1:
        SITE = sys.argv[1]
    app.debug=True
    app.run(host="0.0.0.0", port=5001)
else:
    run_init(SITE)

