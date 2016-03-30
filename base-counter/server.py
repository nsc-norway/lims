#!/usr/bin/python

import datetime
import time
import os

import illuminate
from flask import Flask, render_template, url_for, request, Response, redirect


RUN_STORAGE = "/data/runScratch.boston"

app = Flask(__name__)


class RunBaseCounter(object):

    def __init__(self, run_id):
        self.run_id = run_id
        self.run_dir = os.path.join(RUN_STORAGE, run_id)
        self.last_update = 0
        self.booked = 0
        self.rate = 0
        self.read_config = []
        self.current_cycle = 0
        self.total_cycles = 0
        self.data_cycles_lut = [0]

    def set_metadata(self):
        ds = illuminate.InteropDataset(self.run_dir)
        self.read_config = list(ds.meta.read_config)
        self.total_cycles = sum(read['cycles'] for read in self.read_config)
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

    def update_clusters_pf(ds, process, current_cycle):
        try:
            all_df = ds.TileMetrics().df
        except ValueError:
            return # No information yet
        df = all_df[all_df.code == 103] # Number of clusters PF
        r1cycles = process.udf['Read 1 Cycles']
        reads = 1
        if current_cycle > r1cycles:
            reads = 2

        lanes = process.all_inputs(resolve=True)
        for lane_ana in lanes:
            lane_str = lane_ana.location[1].split(":")[0]
            if lane_str == "A":
                lane = 1
            else:
                lane = int(lane_str)
            clusters = df[df.lane == lane].value.sum()
            for i_read in range(1, reads+1):
                lane_ana.udf['Clusters PF R%d' % i_read] = clusters
        lims.put_batch(lanes)

    def update(self):
        if not self.read_config:
            self.set_metadata()
        self.current_cycle = self.get_cycle()
        self.clusters = self.get_clusters()
        self.booked = self.current_cycle * self.clusters
        self.last_update = time.time()

    @property
    def projected_rate(self):
        pass

    @property
    def basecount(self):
        return self.booked + (self.rate * (time.time() - self.last_update))


@app.route("/")
def get_main():
    return redirect(url_for('static', filename='index.xhtml'))


def event(rbc):
    i=0
    while True:
        rbc.update()
        event = "event: run.%s\n" % (rbc.run_id)
        print "bc", rbc.basecount
        print "rate", rbc.rate
        event += 'data: {"basecount": %d, "rate": %d}\n\n' % (
                rbc.basecount,
                rbc.rate
                )
        yield event
        time.sleep(2)


@app.route("/status")
def get_status():
    rbc = RunBaseCounter("160329_M01132_0133_000000000-AMY9J")
    return Response(event(rbc), mimetype="text/event-stream")

if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", port=5001, threaded=True)

