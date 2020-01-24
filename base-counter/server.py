#!/usr/bin/python

import json
import datetime
import time
import os
import threading
import glob
import re
import math
import blinker
import Queue
import weakref
import bitstring
import subprocess

import _strptime # Prevent import in thread

from functools import partial
from operator import itemgetter

import illuminate
from flask import Flask, url_for, redirect, jsonify, Response, request


RUN_STORAGE = "/data/runScratch.boston"

SEQUENCER_LIST = [
    ('A00943', ('novaseq', 'Nordis')),

    ('M01132', ('miseq', 'Milo')),
    ('M01334', ('miseq', 'Mina')),
    ('M02980', ('miseq', 'Mike')),

    ('NS500336', ('nextseq', 'Nemo')),
    ('NB501273', ('nextseq', 'Nelson')),

    ('J00146', ('hiseq3k', 'Hiawatha')),
    ('E00401', ('hiseq4k', 'Hippo')),

    ('E00426', ('hiseqx', 'Pixie')),
    ('E00423', ('hiseqx', 'Roxanne')),
    ]

SEQUENCERS = dict(SEQUENCER_LIST)

app = Flask(__name__)
db = None # Set on bottom of script

def updater():
    """Updater background thread"""

    while True:
        db.update()
        time.sleep(61)

MAX_ACTIVE_STREAMS = 19
active_streams = []
KEEPALIVE_INTERVAL = 60 # Times sleep interval 61

def machine_id(run_id):
    return re.match(r"\d{6}_([A-Z0-9]+)_.*", run_id).group(1)

class Database(object):
    """Persistent storage for some run data."""

    COUNT_FILE = "/var/db/nsc-status/count.txt"
    BOOKED_RUNS_FILE = "/var/db/nsc-status/booked.txt"
    CANCELLED_RUNS_FILE = "/var/db/nsc-status/cancelled.txt"

    def __init__(self):
        self.completed = set()
        self.status = {}
        self.basecount_signal = blinker.Signal()
        self.run_status_signal = blinker.Signal()
        self.machine_list_signal = blinker.Signal()
        self.keepalive_counter = 0
        try:
            with open(self.COUNT_FILE) as f:
                self.count = int(f.read())
        except IOError:
            self.count = 0
        try:
            with open(self.BOOKED_RUNS_FILE) as f:
                self.booked_runs = set(r.strip() for r in f.readlines())
        except IOError:
            self.booked_runs = set()
        try:
            with open(self.CANCELLED_RUNS_FILE) as f:
                self.cancelled_runs = set(r.strip() for r in f.readlines())
        except IOError:
            self.cancelled_runs = set()

    def update(self):
        with open(self.COUNT_FILE) as f:
            self.count = int(f.read())

        runs_on_storage = set((
                os.path.basename(os.path.dirname(rpath)) for rpath in
                glob.glob(os.path.join(RUN_STORAGE, "??????_*_*", "*"))
                ))
        new = runs_on_storage - set(self.status.keys())

        for r_id in new:
            new_run = RunStatus(r_id, start_cancelled=r_id in self.cancelled_runs)
            self.status[r_id] = new_run

        modified = False
        updated = []
        for r in self.status.values():
            if r.update():
                updated.append(r)
            if r.finished and not r.committed:
                try:
                    if not r.run_id in self.booked_runs:
                        self.increment(r.basecount)
                        self.booked_runs.add(r.run_id)
                finally:
                    r.committed = True
                modified = True

        missing = set(self.status.keys()) - runs_on_storage
        for r_id in missing:
            if not self.status[r_id].is_fake:
                del self.status[r_id]
                self.booked_runs.discard(r_id)

        self.booked_runs &= set(self.status.keys())
        new_cancelled_runs = set(k for (k, v) in self.status.items() if v.cancelled)
        if new_cancelled_runs != self.cancelled_runs:
            self.cancelled_runs = new_cancelled_runs
            modified = True

        if modified:
            self.save()

        if new or missing:
            self.machine_list_signal.send(self, data=self.machine_list)

        if updated or self.keepalive_counter > KEEPALIVE_INTERVAL:
            self.keepalive_counter = 0
            self.basecount_signal.send(self, data=self.global_base_count)
            for r in updated:
                self.run_status_signal.send(self, data=r.data_package)

    def increment(self, bases):
        self.count += bases

    def save(self):
        with open(self.COUNT_FILE, 'w') as f:
            f.write(str(int(self.count)))
        with open(self.BOOKED_RUNS_FILE, 'w') as f:
            f.writelines("\n".join(self.booked_runs))
        with open(self.CANCELLED_RUNS_FILE, 'w') as f:
            f.writelines("\n".join(self.cancelled_runs))

    @property
    def global_base_count(self):
        rate = sum(run.rate for run in self.status.values())
        count = self.count + sum(run.basecount for run in self.status.values() if not run.committed)
        return {'count': count, 'rate': rate}

    @property
    def machine_list(self):
        machines = {}
        for m_id, (m_type, m_name) in SEQUENCER_LIST:
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
        #return list(reversed(sorted(machines.values(), key=lambda x: (not x['type'].startswith("-"), x['run_ids']))))
        # Don't sort machines, use fixed order as in config
        return [machines[m_id] for m_id, _ in SEQUENCER_LIST]



def instrument_rate(m_id):
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
    elif instrument == "novaseq":
        per_hour = 3125000000
    return per_hour / 3600.0

class RunStatus(object):

    public = ['machine_id', 'run_id', 'run_dir', 'read_config', 'current_cycle',
            'total_cycles', 'basecount', 'rate', 'finished', 'cancelled']

    def __init__(self, run_id, start_cancelled=False):
        self.machine_id = machine_id(run_id)
        self.run_id = run_id
        self.run_dir = os.path.join(RUN_STORAGE, run_id)
        self.read_config = []
        self.current_cycle = 0
        self.total_cycles = 0
        self.clusters = 0

        self.last_update = time.time()
        self.booked = 0
        self.committed = False  # Is base count added to grand total?
        self.data_cycles_lut = [0]
        self.start_time = 0
        self.cycle_arrival = {} # (cycle, time) pairs
        self.finished = False
        self.start_cancelled = start_cancelled
        self.cancelled = start_cancelled

    def set_metadata(self):
        try:
            ds = illuminate.InteropDataset(self.run_dir)
        except:
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
        instrument = SEQUENCERS[self.machine_id][0]
        if instrument == "novaseq":
            process = subprocess.Popen(['nsc-python27', 
                            '/opt/gls/clarity/customextensions/lims/base-counter/clusters-helper.py',
                             self.run_dir],
                        stdout=subprocess.PIPE, stderr=open(os.devnull, 'w'))
            try:
                out, err = process.communicate()
                val = float(out)
                return None if math.isnan(val) else val
            except (subprocess.CalledProcessError, ValueError):
                return None
        try:
            ds = illuminate.InteropDataset(self.run_dir)
            all_df = ds.TileMetrics().df
        except (ValueError, TypeError, IOError, bitstring.ReadError):
            return None # No information yet, or it's being written to
        return all_df[all_df.code == 103].sum().sum() # Number of clusters PF

    def check_finished(self):
        return os.path.exists(os.path.join(self.run_dir, "RTAComplete.txt"))

    def check_cancelled(self):
        """Heuristic to determine if cancelled. If current cycle time is
        more than 2x last cycle time."""

        if len(self.cycle_arrival) <= 1 and self.start_cancelled:
            return True
        if (not self.finished) and len(self.cycle_arrival) > 0:
            current_cycle_time = time.time() - self.cycle_arrival[self.current_cycle]
            if current_cycle_time > 25*3600 or (SEQUENCERS[self.machine_id][0] != 'hiseq' and current_cycle_time > 3600*7):
                return True
            if len(self.cycle_arrival) > 2:
                cycle_rate, cycle_stride = self.get_cycle_rate()
                next_index_cycles = sum(
                        1
                        for i in range(self.current_cycle+1, self.total_cycles)
                        if self.data_cycles_lut[i] == self.data_cycles_lut[self.current_cycle]
                        )
                after_index_read = 0
                if next_index_cycles:
                    after_index_read = 25 # Some slack on start of read 2, takes about 25 cycles before writing on MiSeq
                cancelled = current_cycle_time > (6+after_index_read+next_index_cycles) * (cycle_stride / cycle_rate)
                return cancelled
        return False

    def update(self):
        if self.finished:
            return
        now = time.time()
        updated = False
        initial_update = False
        if not self.read_config:
            updated = self.set_metadata()
            initial_update = updated
            self.start_time = now
        old_cycle = self.current_cycle
        self.current_cycle = self.get_cycle()
        if self.cycle_arrival.setdefault(self.current_cycle, now) == now: # Add if not exists
            updated = True
        new_clusters = self.get_clusters()
        self.clusters = new_clusters or self.clusters
        if self.clusters:
            #self.booked = self.data_cycles_lut[self.current_cycle] * self.clusters
            self.booked = self.current_cycle * self.clusters
        else:
            self.booked = 0

        if self.check_finished():
            self.finished = True
            updated = True
        new_cancelled = self.check_cancelled()
        if new_cancelled != self.cancelled:
            self.cancelled = new_cancelled
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

        if len(self.cycle_arrival) > 2 and self.clusters != 0:
            mean_cycle_rate, mean_stride = self.get_cycle_rate()

            #next_data_cycles = self.data_cycles_lut[
            #        min(self.current_cycle+int(mean_stride), self.total_cycles)
            #            ]
            next_data_cycles = min(self.current_cycle+int(mean_stride), self.total_cycles)
            #data_factor = (next_data_cycles - self.data_cycles_lut[self.current_cycle]) / mean_stride
            data_factor = (next_data_cycles - self.current_cycle) / mean_stride

            return self.clusters * mean_cycle_rate * data_factor
        elif len(self.cycle_arrival) != 0:
            return instrument_rate(self.machine_id)
        else:
            return 0

    @property
    def basecount(self):
        """Estimated number of bases at this instant"""
        if len(self.cycle_arrival) > 3 or self.current_cycle > 29:
            return self.booked + (self.rate * (time.time() - self.last_update))
        elif len(self.cycle_arrival) >= 1:
            return self.rate * (time.time() - self.start_time)
        else:
            return 0

    @property
    def data_package(self):
        """Dict to be sent to clients"""

        return dict((key, getattr(self, key)) for key in RunStatus.public)

    @property
    def is_fake(self):
        return False

class FakeRun(RunStatus):
    """For testing, etc."""

    def __init__(self, machine_id, num_cycles, start_cycle=0):
        run_id = datetime.datetime.now().strftime("%y%m%d_" + machine_id + "_FAKE_%f")
        super(FakeRun, self).__init__(run_id)
        self.num_cycles = num_cycles
        self.start_time = time.time()
        self.start_cycle = start_cycle

    def set_metadata(self):
        self.read_config = True # See if we can get away with it
        self.total_cycles = self.num_cycles
        # Build look-up table for number of cycles -> number of data cycles
        self.data_cycles_lut = [(i, i) for i in xrange(self.num_cycles+1)]
        return True

    def get_clusters(self):
        m_t = SEQUENCERS[self.machine_id][0]
        if m_t == "hiseq":
            return 2e9
        elif m_t == "hiseqx":
            return 2.6e9
        elif m_t in ["hiseq4k", "hiseq3k"]:
            return 2.1e9
        elif "nextseq":
            return 400e6
        elif "miseq":
            return 25e6
        elif "novaseq":
            return 3.3e9 # 3.3 billion reads, spec S2 flow cell

    def get_cycle(self):
        speed = instrument_rate(self.machine_id) / self.get_clusters()
        return int(min(self.start_cycle + (time.time() - self.start_time) * speed, self.total_cycles))

    def check_finished(self):
        return False

    @property
    def is_fake(self):
        return True


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

    TERMINATE = object()

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
        if ident is self.TERMINATE:
            raise StopIteration()
        event_str = ""
        if ident is not None:
            event_str = "event: " + ident + "\n"
        event_str += 'data: ' + json.dumps(data) + '\n\n'
        return event_str

    def update(self, ident, sender=None, data=None):
        self.queue.put((ident, data))

    def terminate(self):
        self.queue.put((self.TERMINATE, None))


@app.route("/")
def get_main():
    return redirect(url_for('static', filename='index.html'))


@app.route("/status")
def status():
    global active_streams
    active_streams = [stream for stream in active_streams if stream() is not None]
    while len(active_streams) >= MAX_ACTIVE_STREAMS:
        (active_streams.pop(0))().terminate()
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
    active_streams.append(weakref.ref(stream))
    return Response(stream, mimetype="text/event-stream")

@app.route("/machines")
def machines():
    return jsonify(SEQUENCERS)

@app.route("/fake", methods=['POST'])
def fake():
    params = request.json
    run = FakeRun(params['machine'], int(params['cycles']), int(params['start_cycle']))
    db.status[run.run_id] = run
    db.update()
    return "OK"

@app.route("/fake-runs")
def fakes():
    return jsonify(runs=[run.run_id for run in db.status.values() if isinstance(run, FakeRun)])

@app.route("/delete", methods=['POST'])
def delete():
    params = request.json
    del db.status[params['id']]
    return "OK"

db = Database()
updater_thread = threading.Thread(target=updater, name="updater")
updater_thread.daemon = True
updater_thread.start()

if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", port=5001, threaded=True)
