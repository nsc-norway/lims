#!/usr/bin/python

import json
import datetime
import time
import os
import threading
import glob
import re
import blinker
import Queue

from operator import itemgetter

import illuminate
from flask import Flask, url_for, redirect, jsonify, Response


RUN_STORAGE = "/data/runScratch.boston"


SEQUENCERS = {
    '7001448': ('hiseq', 'Hillary'),
    'D00132': ('hiseq', 'Hilma'),

    'NS500336': ('nextseq', 'Nemo'),
    'NB501273': ('nextseq', 'Nellie (?)'),

    'M01132': ('miseq', 'Milo'),
    'M01334': ('miseq', 'Mina'),
    'M02980': ('miseq', 'Mike'),

    'J00146': ('hiseq3k', 'Trevor (?)'),

    'E00401': ('hiseqx', 'Xenia (?)')
    }


app = Flask(__name__)
db = None # Set on bottom of script

def updater():
    """Updater background thread"""

    while True:
        db.update()
        time.sleep(61)


class Database(object):
    """Persistent storage for some run data."""

    COUNT_FILE = "/var/db/nsc-status/count.txt"

    def __init__(self):
        self.completed = set()
        self.status = {}
        self.signal = blinker.Signal()
        try:
            with open(self.COUNT_FILE) as f:
                self.count = int(f.read())
        except IOError:
            self.count = 0

    def update(self):
        runs_on_storage = set((
                os.path.basename(rpath) for rpath in
                glob.glob(os.path.join(RUN_STORAGE, "??????_*_*"))
                ))
        new = runs_on_storage - set(self.status.keys())

        for r in new:
            new_run = RunStatus(r)
            if new_run.finished:
                # If completed run suddenly appears, assume that it has
                # already bene booked
                self.committed = True
            self.status[r] = new_run

        for r in self.status.values():
            r.update()

        missing = set(self.status.keys()) - runs_on_storage
        modified = False
        for r in missing:
            if not self.status[r].committed:
                # Normally only commit when runs disappear
                self.increment(self.status[r].basecount)
                modified = True
                del self.status[r]

        if modified:
            self.signal.send()
            self.save()

    def increment(self, bases):
        self.count += bases

    def save(self):
        with open(self.COUNT_FILE, 'w') as f:
            f.write(str(self.count))

    def global_base_count(self):
        rate = sum(run.rate for run in self.status.values())
        return {'count': self.count, 'rate': rate}


def instrument_rate(run_id):
    return 1000


class RunStatus(object):

    public = ['run_id', 'run_dir', 'read_config', 'current_cycle',
            'total_cycles', 'basecount', 'rate']

    def __init__(self, run_id):
        self.run_id = run_id
        self.run_dir = os.path.join(RUN_STORAGE, run_id)
        self.read_config = []
        self.current_cycle = 0
        self.total_cycles = 0

        self.last_update = 0
        self.booked = 0
        self.committed = False  # Is base count added to grand total?
        self.data_cycles_lut = [0]
        self.cycle_arrival = {} # (cycle, time) pairs
        self.finished = False
        self.signal = blinker.Signal()

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
        if self.finished:
            return
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
        if self.clusters:
            self.booked = self.current_cycle * self.clusters
        else:
            self.booked = 0
        self.last_update = now

        if os.path.exists(os.path.join(self.run_dir, "RTAComplete.txt")):
            self.finished = True
        if updated:
            self.signal.send()
        return updated

    @property
    def rate(self):
        """Bases per second"""

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
        """Estimated number of bases at this instant"""

        return self.booked + (self.rate * (time.time() - self.last_update))

    def data_package(self):
        """Dict to be sent to clients"""

        return dict((key, getattr(self, key)) for key in RunStatus.public)


class SseStream(object):
    """Usees a Queue to translate between a signal (method call
    interface) and a generator protocol.

    Every time a signal is received, the data function is called,
    and the result is JSON encoded and returned to the stream as
    a SSE."""

    def __init__(self, signal, data_function):
        self.signal = signal
        self.data_function = data_function
        self.first = True
        self.queue = Queue.Queue()
        self.queue.put(self.data_function())
        signal.connect(self.update)

    def __iter__(self):
        return self

    def next(self):
        data = self.queue.get(block=True)
        print "Sending update: ", data
        return 'data: ' + json.dumps(data) + '\n\n'

    def update(self, data):
        self.queue.put(self.data_function())


@app.route("/")
def get_main():
    return redirect(url_for('static', filename='index.html'))

def get_machine_list():
    machines = {}
    for m_id, (m_type, m_name) in SEQUENCERS.items():
        run_ids = [
            run_id for run_id in sorted(db.status.keys())[::-1]
            if re.match("\\d{6}_%s_.*" % (m_id), run_id)
            ]
        machines[m_id] = {
            'id': m_id,
            'name': m_name,
            'type': m_type,
            'run_ids': run_ids
            }

    # Sort machines with newest runs first
    return list(reversed(sorted(machines.values(), key=lambda x: x['run_ids'])))

@app.route("/status/machines")
def machine_list():
    return Response(
        SseStream(db.signal, get_machine_list),
        mimetype="text/event-stream"
        )

@app.route("/status/runs/<run_id>")
def run_status(run_id):
    run_status = db.status.get(run_id)
    if run_status:
        return Response(
                SseStream(run_status.signal, run_status.data_package),
                mimetype="text/event-stream"
                )
    else:
        return "No such run", 404

@app.route("/status/count")
def get_count():
   return Response(
           SseStream(db.signal, db.global_base_count),
           mimetype="text/event-stream"
           )


db = Database()
updater_thread = threading.Thread(target=updater, name="updater")
updater_thread.daemon = True
updater_thread.start()

if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", port=5001, threaded=True)
