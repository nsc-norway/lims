# Assign to demultiplexing workflow and start a step

import sys
import re
import time
from genologics.lims import *
from genologics import config

try:
    SITE = open("/etc/pipeline-site").read().strip()
except IOError:
    SITE = "unknown"

if SITE == "ous":
    SEQ_PROCESSES = [
            "MiSeq Run (MiSeq) NSC 5.1",
            "NextSeq 500/550 Run NSC 3.0",
            "Illumina Sequencing (HiSeq 3000/4000) 1.0",
            "Illumina Sequencing (HiSeq X) 1.0"
            ]
else:
    SEQ_PROCESSES = [
            "Illumina Sequencing (HiSeq 3000/4000) 1.0"
            ]

DEMULTIPLEXING = "Demultiplexing and QC NSC 2.0"
WORKFLOW_NAME = "Demultiplexing and QC 2.0"

def start_step(lims, analytes, workflow):
    protocol = workflow.protocols[0]
    ps = protocol.steps[0]
    queue = ps.queue()
    for attempt in xrange(3):
        if set(analytes) <= set(queue.artifacts):
            lims.create_step(ps, analytes)
            break
        else:
            time.sleep(1)
            queue.get(force=True)


def main():
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    workflows = lims.get_workflows(name=WORKFLOW_NAME)
    workflow = workflows[0]
    for seq in SEQ_PROCESSES:
        procs = lims.get_processes(type=seq, udf={'Monitor': True})

        for proc in procs:
            # Check if there's already a demultiplexing
            demux = lims.get_processes(type=DEMULTIPLEXING, inputartifactlimsid=[input.id for input in proc.all_inputs()])
            if not demux:
                analytes = proc.all_inputs(unique=True)
                lims.route_analytes(analytes, workflow)
                start_step(lims, analytes, workflow)

main()

