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

import _strptime # Prevent import in thread

from functools import partial
from operator import itemgetter

import illuminate
from flask import Flask, url_for, redirect, jsonify, Response


RUN_STORAGE = "/data/runScratch.boston"


SEQUENCERS = {
    '7001448': ('hiseq', 'Hillary'),
    'D00132': ('hiseq', 'Hilma'),

    'NS500336': ('nextseq', 'Nemo'),
    'NB501273': ('nextseq', 'NextSeq (?)'),

    'M01132': ('miseq', 'Milo'),
    'M01334': ('miseq', 'Mina'),
    'M02980': ('miseq', 'Mike'),

    'J00146': ('hiseq3k', 'HiSeq 3000 (?)'),

    'E00401': ('hiseqx', 'HiSeq X (?)')
    }


app = Flask(__name__)
db = None # Set on bottom of script

def updater():
    """Updater background thread"""

    while True:
        db.update()
        time.sleep(61)


def machine_id(run_id):
    return re.match(r"\d{6}_([A-Z0-9]+)_.*", run_id).group(1)

class Database(object):
    """Persistent storage for some run data."""

    COUNT_FILE = "/var/db/nsc-status/count.txt"

    def __init__(self):
        self.completed = set()
        self.status = {}
        self.basecount_signal = blinker.Signal()
        self.run_status_signal = blinker.Signal()
        self.machine_list_signal = blinker.Signal()
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
            self.status[r] = new_run

        modified = False
        updated = []
        for r in self.status.values():
            if r.update():
                updated.append(r)
            if r.finished and not r.committed:
                try:
                    self.increment(self.status[r].basecount)
                finally:
                    r.committed = True
                modified = True

        missing = set(self.status.keys()) - runs_on_storage
        for r in missing:
            del self.status[r]

        if modified:
            self.save()

        if new or missing:
            self.machine_list_signal.send(self, data=self.machine_list)

        if updated:
            self.basecount_signal.send(self, data=self.global_base_count)
            for r in updated:
                self.run_status_signal.send(self, data=r.data_package)

    def increment(self, bases):
        self.count += bases

    def save(self):
        with open(self.COUNT_FILE, 'w') as f:
            f.write(str(int(self.count)))

    @property
    def global_base_count(self):
        rate = sum(run.rate for run in self.status.values())
        count = self.count + sum(run.basecount for run in self.status.values())
        return {'count': count, 'rate': rate}

    @property
    def machine_list(self):
        machines = {}
        for m_id, (m_type, m_name) in SEQUENCERS.items():
            run_ids = [
                run_id for run_id in sorted(self.status.keys())[::-1]
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



def instrument_rate(run_id):
    m_id = machine_id(run_id)
    instrument = SEQUENCERS[m_id][0]
    if instrument == "hiseqx":
        per_hour = 12500000000
    elif instrument == "hiseq4k" or instrument == "hiseq3k":
        per_hour = 8928571428
    elif instrument == "hiseq":
        per_hour = 3472222222
    elif instrument == "nextseq":
        per_hour = 4137931034
    elif instrument == "miseq":
        per_hour = 133928571
    return per_hour / 3600.0

class RunStatus(object):

    public = ['machine_id', 'run_id', 'run_dir', 'read_config', 'current_cycle',
            'total_cycles', 'basecount', 'rate', 'finished', 'cancelled']

    def __init__(self, run_id):
        self.machine_id = machine_id(run_id)
        self.run_id = run_id
        self.run_dir = os.path.join(RUN_STORAGE, run_id)
        self.read_config = []
        self.current_cycle = 0
        self.total_cycles = 0

        self.last_update = time.time()
        self.booked = 0
        self.committed = False  # Is base count added to grand total?
        self.data_cycles_lut = [0]
        self.cycle_arrival = {} # (cycle, time) pairs
        self.finished = False

    def set_metadata(self):
        try:
            ds = illuminate.InteropDataset(self.run_dir)
        except IOError:
            return False
        self.read_config = list(ds.meta.read_config)
        self.total_cycles = sum(read['cycles'] for read in self.read_config)
        # Build look-up table for number of cycles -> number of data cycles
        for read in self.read_config:
            base = self.data_cycles_lut[-1]
            if read['is_index']:
                self.data_cycles_lut += [base] * read['cycles']
            else:
                self.data_cycles_lut += range(base+1, base+1+read['cycles'])

        return self.total_cycles != 0

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
        try:
            ds = illuminate.InteropDataset(self.run_dir)
            all_df = ds.TileMetrics().df
        except (ValueError, TypeError, IOError):
            return None # No information yet
        return all_df[all_df.code == 103].sum().sum() # Number of clusters PF

    def update(self):
        if self.finished or self.cancelled:
            return
        now = time.time()
        updated = False
        initial_update = False
        if not self.read_config:
            updated = self.set_metadata()
            initial_update = updated
        old_cycle = self.current_cycle
        self.current_cycle = self.get_cycle()
        if self.cycle_arrival.setdefault(self.current_cycle, now) == now: # Add if not exists
            updated = True
        self.clusters = self.get_clusters()
        if self.clusters:
            #self.booked = self.data_cycles_lut[self.current_cycle] * self.clusters
            self.booked = self.current_cycle * self.clusters
        else:
            self.booked = 0

        if os.path.exists(os.path.join(self.run_dir, "RTAComplete.txt")):
            self.finished = True
            updated = True
        if updated:
            if self.clusters != 0 or initial_update:
                self.last_update = now
        return updated

    def get_cycle_rate(self):
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
        return mean_cycle_rate, mean_stride

    @property
    def rate(self):
        """Bases per second"""

        if self.finished or self.cancelled:
            return 0

        if len(self.cycle_arrival) > 1 and self.clusters != 0:
            mean_cycle_rate, mean_stride = self.get_cycle_rate()

            #next_data_cycles = self.data_cycles_lut[
            #        min(self.current_cycle+int(mean_stride), self.total_cycles)
            #            ]
            next_data_cycles = min(self.current_cycle+int(mean_stride), self.total_cycles)
            #data_factor = (next_data_cycles - self.data_cycles_lut[self.current_cycle]) / mean_stride
            data_factor = (next_data_cycles - self.current_cycle) / mean_stride

            return self.clusters * mean_cycle_rate * data_factor
        elif self.total_cycles != 0:
            return instrument_rate(self.run_id)
        else:
            return 0

    @property
    def basecount(self):
        """Estimated number of bases at this instant"""

        return self.booked + (self.rate * (time.time() - self.last_update))

    @property
    def cancelled(self):
        """Heuristic to determine if cancelled. If current cycle time is
        more than 2x last cycle time."""

        if not self.finished and len(self.cycle_arrival) > 2:
            current_cycle_time = time.time() - self.cycle_arrival[self.current_cycle]
            if current_cycle_time > 12*3600:
                return True
            cycle_rate, cycle_stride = self.get_cycle_rate()
            cancelled = current_cycle_time > 2 * (cycle_stride / cycle_rate)
            return cancelled
        else:
            return False

    @property
    def data_package(self):
        """Dict to be sent to clients"""

        return dict((key, getattr(self, key)) for key in RunStatus.public)


class EventQueuer(object):
    """Helper class encapsulates a single type of signal, conversion
    to queue data."""

    def __init__(self, queue, ident):
        self.queue = queue
        self.ident = ident

    def __call__(self, sender, data):
        self.queue.put((self.ident, data))

class SseStream(object):
    """Usees a Queue to translate between a signal (method call
    interface) and a generator protocol.

    This new version of SSE Stream can multiplex multiple signals
    onto the event stream, setting the id of each event as appropriate.
    The constructor argument is a list of event type sepecifications,
    encoded as tuples:
        (SIGNAL, ID)
    Every time a signal is received, the data of the event is JSON
    encoded and returned to the stream as a SSE, with the specified
    ID ("event:" line).

    The ID can be None, in which case no ID is sent.
    """

    def __init__(self, event_specs):
        self.queue = Queue.Queue()
        self.helpers = []
        for signal, ident in event_specs:
            qr = EventQueuer(self.queue, ident)
            signal.connect(qr)
            self.helpers.append(qr)

    def __iter__(self):
        return self

    def next(self):
        ident, data = self.queue.get(block=True)
        event_str = ""
        if ident is not None:
            event_str = "event: " + ident + "\n"
        event_str += 'data: ' + json.dumps(data) + '\n\n'
        return event_str

    def update(self, ident, sender=None, data=None):
        self.queue.put((ident, data))

@app.route("/")
def get_main():
    return redirect(url_for('static', filename='index.html'))


@app.route("/status")
def status():
    events = [
        (db.basecount_signal, "basecount"),
        (db.run_status_signal, "run_status"),
        (db.machine_list_signal, "machine_list")
    ]
    stream = SseStream(events)
    # Send initial status
    stream.update("basecount", data=db.global_base_count)
    stream.update("machine_list", data=db.machine_list)
    for r in db.status.values():
        stream.update("run_status", data=r.data_package)
    return Response(stream, mimetype="text/event-stream")


db = Database()
updater_thread = threading.Thread(target=updater, name="updater")
updater_thread.daemon = True
updater_thread.start()

if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", port=5001, threaded=True)
