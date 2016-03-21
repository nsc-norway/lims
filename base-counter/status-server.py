#!/usr/bin/python

from flask import Flask, render_template, url_for, request, Response, redirect
from genologics.lims import *
from genologics import config
import datetime
import time

BASELINE_FILE = "/var/db/nsc-status/basecount.txt"

app = Flask(__name__)

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

class BaseCounter(object):

    def __init__(self):
        with open(BASELINE_FILE, "r") as basecount_file:
            self.basecount = int(basecount_file.read().strip())

        self.basecount_file = open(BASELINE_FILE, "w")

    def get(self):
        return count

    def write(self):
        self.basecount_file.seek(0)
        self.basecount_file.write(str(self.basecount) + "\n")

BASELINE_PATH = "/var/db/nsc-status/baseline.txt"
baseline_file = None
basecount = 0

def init():
    global baseline_file, basecount
    try:
        with open(BASELINE_FILE) as baseline_file:
            basecount = int(baseline_file.read())
    except (IOError, ValueError):
        basecount = 0

def update_bases():
    pass


@app.route("/")
def get_main():
    return redirect(url_for('static', filename='index.xhtml'))


def event():
    i=0
    while True:
        yield "data: %d\n\n" % (i)
        i += 1
        time.sleep(2)


@app.route("/status")
def get_status():
    return Response(event(), mimetype="text/event-stream")

init()

if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", port=5001, threaded=True)

