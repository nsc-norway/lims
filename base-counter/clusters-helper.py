#!/usr/bin/nsc-python27
import sys
from interop import py_interop_run_metrics, py_interop_run, py_interop_summary


run_dir = sys.argv[1]

valid_to_load = py_interop_run.uchar_vector(py_interop_run.MetricCount, 0)
py_interop_run_metrics.list_summary_metrics_to_load(valid_to_load)
valid_to_load[py_interop_run.ExtendedTile] = 1
run_metrics = py_interop_run_metrics.run_metrics()
run_metrics.read(run_dir, valid_to_load)
summary = py_interop_summary.run_summary()
py_interop_summary.summarize_run_metrics(run_metrics, summary)
read_data = summary.at(0)
clusters = 0
for lane in range(summary.lane_count()):
    clusters += read_data.at(lane).reads_pf()
print clusters

