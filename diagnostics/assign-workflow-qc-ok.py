# Assign sequenced diagnostics samples to interpretation workflow

import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id, workflow_name):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    workflows = lims.get_workflows(name=workflow_name)
    try:
        workflow = workflows[0]
    except IndexError:
        print "Unknown workflow '", workflow_name, "'"
        sys.exit(1)
    qc_ok_inputs = (ana for ana in process.all_inputs(unique=True, resolve=True) if ana.qc_flag=="PASSED")
    samples = [s for ana in qc_ok_inputs for s in ana.samples]
    lims.get_batch(samples)
    diag_samples = [s for s in samples if s.project.name.startswith("Diag-")]
    root_analytes = (s.artifact for s in diag_samples)

    lims.route_analytes(root_analytes, workflow)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

