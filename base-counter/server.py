#!/usr/bin/python

import json
import datetime
import time
import os
import threading

from operator import itemgetter

import illuminate
from flask import Flask, url_for, redirect, jsonify, Response


RUN_STORAGE = "/data/runScratch.boston"

app = Flask(__name__)

active_runs = {}

def updater():
    """Updater background thread"""

    active_runs["160329_M02980_0056_000000000-AMT90"] =\
                RunStatus("160329_M02980_0056_000000000-AMT90")
    while True:
        time.sleep(60)
        for rs in active_runs.values():
            rs.update()

class GlobalBaseCounter(object):
    pass


def instrument_rate(run_id):
    return 1000


class RunStatus(object):

    def __init__(self, run_id):
        self.run_id = run_id
        self.run_dir = os.path.join(RUN_STORAGE, run_id)
        self.last_update = 0
        self.booked = 0
        self.read_config = []
        self.current_cycle = 0
        self.total_cycles = 0
        self.data_cycles_lut = [0]
        self.cycle_arrival = {} # (cycle, time) pairs
        self.condition = threading.Condition()

    def set_metadata(self):
        ds = illuminate.InteropDataset(self.run_dir)
        self.read_config = list(ds.meta.read_config)
        self.total_cycles = sum(read['cycles'] for read in self.read_config)
        # Build look-up table for number of cycles -> number of data cycles
        for read in self.read_config:
            base = self.data_cycles_lut[-1]
            if read['is_index']:
                self.data_cycles_lut += [base] * read['cycles']
            else:
                self.data_cycles_lut += range(base+1, base+1+read['cycles'])

    def get_cycle(self):
        for cycle in range(self.current_cycle, self.total_cycles):
            test_paths = [
                    os.path.join(
                        self.run_dir, "Data", "Intensities", "BaseCalls", "L001",
                        "C{0}.1".format(cycle+1)
                        ),
                    os.path.join(
                        self.run_dir, "Data", "Intensities", "BaseCalls", "L001",
                        "{0:04d}.bcl.bgzf".format(cycle+1)
                        )
                    ]
            if not any(os.path.exists(test_path) for test_path in test_paths):
                return cycle
        return self.total_cycles

    def get_clusters(self):
        ds = illuminate.InteropDataset(self.run_dir)
        try:
            all_df = ds.TileMetrics().df
        except ValueError:
            return # No information yet
        return all_df[all_df.code == 103].sum().sum() # Number of clusters PF

    def update(self):
        now = time.time()
        updated = False
        if not self.read_config:
            self.set_metadata()
            updated = True
        old_cycle = self.current_cycle
        self.current_cycle = self.get_cycle()
        if self.cycle_arrival.setdefault(self.current_cycle, now) == now: # Add if not exists
            updated = True
        self.clusters = self.get_clusters()
        self.booked = self.current_cycle * self.clusters
        self.last_update = now

        if updated:
            with self.condition:
                self.condition.notify_all()

        return updated


    @property
    def rate(self):
        print self.cycle_arrival
        if len(self.cycle_arrival) > 1:
            # Difference in cycle, time
            # Here, we look at all cycles, including index cycles, 
            # to estimate the speed of the sequencer
            cycle_arrival_list = sorted(self.cycle_arrival.items(), key=itemgetter(0))
            dcs, dts = zip(*[
                    (
                        (a2[0] - a1[0]),
                        (a2[1] - a1[1])
                    )
                for a1, a2 in 
                zip(
                    cycle_arrival_list,
                    cycle_arrival_list[1:]
                    )
                ])
            # Mean cycles per update for last 5 updates
            # Typically this will be unity, unless updates are run very infrequently
            mean_stride = sum(dcs[-5:]) / min(len(dcs), 5)
            # Total rate (index + data cycles per time)
            mean_cycle_rate = sum(dcs[-5:]) / sum(dts[-5:])

            next_data_cycles = self.data_cycles_lut[
                    min(self.current_cycle+int(mean_stride), self.total_cycles)
                        ]
            data_factor = (next_data_cycles - self.data_cycles_lut[self.current_cycle]) / mean_stride

            return self.clusters * mean_cycle_rate * data_factor
        else:
            return instrument_rate(self.run_id)

    @property
    def basecount(self):
        return self.booked + (self.rate * (time.time() - self.last_update))

    @property
    def finished(self):
        return self.current_cycle == self.total_cycles
    
    def wait_for_update(self):
        with self.condition:
            self.condition.wait()

    @property
    def data_package(self):
        pass


@app.route("/")
def get_main():
    return redirect(url_for('static', filename='index.xhtml'))


@app.route("/status/runs")
def run_list():
    return jsonify({"runs": active_runs.keys()})


def event(rs):
    i=0
    while True:
        rs.update()
        event = 'data: {"basecount": %d, "rate": %d, "active": %d}\n\n' % (
                rs.basecount,
                rs.rate,
                int(not rs.finished)
                )
        print event,
        yield event
        rs.wait_for_update()

        
@app.route("/status/runs/<run_id>")
def run_status(run_id):
    rs = active_runs.get(run_id)
    if rs:
        return Response(event(rs), mimetype="text/event-stream")
    else:
        return 404

updater_thread = threading.Thread(target=updater)
updater_thread.daemon = True
updater_thread.start()

if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", port=5001, threaded=True)

