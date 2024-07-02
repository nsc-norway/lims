#!/bin/env python

# Script to write Lane-level metrics to LIMS.
#
# It parses the InterOp files in the run folder, and posts the metric information to the
# Measurement outputs of the AUTOMATED - NovaSeq Run step.
# ----
# The usage is "unusual" and not obvious:
# - Takes the process ID of a sibling step, in practice "NovaSeq Data QC" step. It then uses the
#   API to locate the inputs / outputs of the NovaSeq Run step. The reason it can't operate
#   directly on NovaSeq Run is that we try to not touch that step, because it may cause
#   disruption of the sequencer integration.

from interop import py_interop_run_metrics, py_interop_run, py_interop_summary
import sys
import re
import os
import yaml
import math
import traceback
from genologics.lims import *
from genologics import config
lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

process_id  = sys.argv[1]
seq_process = Process(lims, id=process_id)

try:
    run_id = seq_process.udf['Run ID']
except KeyError:
    # Something wrong with seq. step -- can't do anything
    sys.exit(0)

using_xp_workflow = len(seq_process.all_inputs(unique=True)) > 1

lane_artifacts = {}
outs = seq_process.all_outputs(unique=True, resolve=True)
if using_xp_workflow:
    for out in outs:
        laneid_re = re.match(r"Lane (\d):\d$", out.name)
        if laneid_re:
            lane_artifacts[int(laneid_re.group(1))] = out
else: # Standard loading workflow
    # Assign lane artifacts in order of outputs (as we get them from LIMS),
    # and also rename the artifacts
    lane_id = 1
    for i, o in seq_process.input_output_maps:
        if o['output-generation-type'] == 'PerInput':
            art = o['uri']
            lane_artifacts[lane_id] = art
            art.name = "Lane {}:1".format(lane_id)
            lane_id += 1

run_dir = "/data/diag/runs/{}".format(run_id)
if not os.path.exists(run_dir):
    print("Run folder {} not found, can't get the InterOp files.".format(run_dir))
    sys.exit(1)

def nan_to_zero(val):
    if math.isnan(val): return 0.0
    else: return val

try: # Ignore parsing error, to not disturb the sequencer integrations

    # Parse InterOp data
    valid_to_load = py_interop_run.uchar_vector(py_interop_run.MetricCount, 0)
    py_interop_run_metrics.list_summary_metrics_to_load(valid_to_load)
    valid_to_load[py_interop_run.ExtendedTile] = 1
    run_metrics = py_interop_run_metrics.run_metrics()
    run_metrics.read(run_dir, valid_to_load)
    summary = py_interop_summary.run_summary()
    py_interop_summary.summarize_run_metrics(run_metrics, summary)
    extended_tile_metrics = run_metrics.extended_tile_metric_set()

    read_count = summary.size()
    lane_count = summary.lane_count()

    if lane_count != len(lane_artifacts):
        raise RuntimeError("Error: Number of lanes in InterOp data: {}, does not match the number "
            "of lanes in LIMS: {}.".format(lane_count, len(lane_artifacts)))

    result = {}
    phix_pct = [] # We report PhiX % per read R1 / R2 (non-index)
    for lane_number, artifact in lane_artifacts.items():
        lane_index = lane_number - 1
        nonindex_read_count = 0
        for read in range(read_count):
            read_data = summary.at(read)
            if not read_data.read().is_index():
                read_label = str(nonindex_read_count + 1)
                lane_summary = read_data.at(lane_index)
                artifact.udf['Yield PF (Gb) R{}'.format(read_label)] = lane_summary.yield_g()
                artifact.udf['% Bases >=Q30 R{}'.format(read_label)] = lane_summary.percent_gt_q30()
                artifact.udf['Cluster Density (K/mm^2) R{}'.format(read_label)] = lane_summary.density().mean()
                artifact.udf['Reads PF (M) R{}'.format(read_label)] = lane_summary.reads_pf() / 1.0e6
                artifact.udf['%PF R{}'.format(read_label)] = lane_summary.percent_pf().mean()
                artifact.udf['Intensity Cycle 1 R{}'.format(read_label)] = lane_summary.first_cycle_intensity().mean()
                artifact.udf['% Error Rate R{}'.format(read_label)] = nan_to_zero(lane_summary.error_rate().mean())
                artifact.udf['% Phasing R{}'.format(read_label)] = nan_to_zero(lane_summary.phasing().mean())
                artifact.udf['% Prephasing R{}'.format(read_label)] = nan_to_zero(lane_summary.prephasing().mean())
                artifact.udf['% Aligned R{}'.format(read_label)] = nan_to_zero(lane_summary.percent_aligned().mean())
                artifact.udf['% Occupied Wells'] = nan_to_zero(lane_summary.percent_occupied().mean())
                nonindex_read_count += 1

    lims.put_batch(lane_artifacts.values())


except Exception as e:
    print("Exception encountered in novaseq-post-run.py, and ignored:")
    traceback.print_exc()

