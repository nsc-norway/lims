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
from genologics.lims import *
from genologics import config
lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

qc_process_id  = sys.argv[1]
qc_process = Process(lims, id=qc_process_id)
qc_input_lanes = qc_process.all_inputs(unique=True)

sib_procs = lims.get_processes(inputartifactlimsid=[qi.id for qi in qc_input_lanes])
for seq_proc in sib_procs:
    if seq_proc.type_name.startswith('AUTOMATED - NovaSeq Run'):
        break
else: # If not breaked
    print("There is no sequencing step.")
    sys.exit(1)

try:
    run_id = seq_proc.udf['Run ID']
except KeyError:
    # Something wrong with seq. step -- can't do anything
    sys.exit(0)

using_xp_workflow = len(seq_proc.all_inputs(unique=True)) > 1

lane_artifacts = {}
outs = seq_proc.all_outputs(unique=True, resolve=True)
if using_xp_workflow:
    for out in outs:
        laneid_re = re.match(r"Lane (\d):\d$", out.name)
        if laneid_re:
            lane_artifacts[int(laneid_re.group(1))] = out
else: # Standard loading workflow
    # Assign lane artifacts in order of outputs (as we get them from LIMS),
    # and also rename the artifacts
    for laneno, art in zip(range(1,5), outs):
        lane_artifacts[laneno] = art
        art.name = "Lane {}:1".format(laneno)

run_dir = "/data/runScratch.boston/{}".format(run_id)
#DEBUG:
run_dir="/data/runScratch.boston/processed/210318_A00943_0185_AH57GNDRXY"
if not os.path.exists(run_dir):
    print("Run folder {} not found, can't get the InterOp files.".format(run_dir))
    sys.exit(1)

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
    print("Number of lanes in InterOp data: {}, does not match the number "
          "of lanes in LIMS: {}.".format(lane_count, len(lane_artifacts)))
    sys.exit(1)

result = {}
phix_pct = [] # We report PhiX % per read R1 / R2 (non-index)
for lane_number, artifact in lane_artifacts.items():
    nonindex_read_count = 0
    raw_density, pf_density, occu_pct_sum = 0, 0, 0
    phix_pct = []
    for read in range(read_count):
        read_data = summary.at(read)
        if not read_data.read().is_index():
            data = read_data.at(lane_number)
            raw_density += data.density().mean()
            pf_density += data.density_pf().mean()
            if nonindex_read_count >= len(phix_pct):
                phix_pct.append(data.percent_aligned().mean())
            else:
                phix_pct[nonindex_read_count] += data.percent_aligned().mean() * 1.0
            nonindex_read_count += 1
    occupancy_lane_metrics = extended_tile_metrics.metrics_for_lane(data.lane())
    if not occupancy_lane_metrics.empty():
        occu_pct_sum += sum(occupancy_lane_metrics[i].percent_occupied() for i in
                                range(occupancy_lane_metrics.size())) \
                                        / occupancy_lane_metrics.size()
    if not merge_lanes:
        result[data.lane()] = LaneStats(
                    raw_density / nonindex_read_count,
                    pf_density / nonindex_read_count,
                    pf_density / max(1, raw_density),
                    phix_pct,
                    occu_pct_sum
                    )
if merge_lanes:
    result["X"] = LaneStats(
                raw_density / (lane_count * nonindex_read_count),
                pf_density / (lane_count * nonindex_read_count),
                pf_density / max(1, raw_density),
                [phix_r / lane_count for phix_r in phix_pct],
                occu_pct_sum / lane_count
                )

lims.put_batch(lane_artifacts.values())