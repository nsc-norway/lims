# Assign sequenced diagnostics samples to interpretation workflow

import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    inputs = list(set(i['uri'].stateless for i, o in process.input_output_maps
                    if o['output-generation-type'] == "PerReagentLabel"))
    lims.get_batch(inputs)
    lims.get_batch(sample for input in inputs for sample in input.samples)
    qc_results = {}
    if any(i.qc_flag == "UNKNOWN" for i in inputs):
        for typ in ["NovaSeq Data QC", "NextSeq 500/550 Run NSC 3.0"]:
            try:
                qc_list = [qc.stateless for qc in lims.get_qc_results_re(inputs, typ)]
                break
            except KeyError: # If missing QC result, get_qc_results_re throws KeyError
                qc_list = []
        if qc_list:
            lims.get_batch(qc_list)
            qc_results = dict(zip(inputs, qc_list))
    routables = []
    for i in inputs:
        if i.qc_flag == "PASSED" or (
                i in qc_results and qc_results[i].qc_flag == "PASSED"
                ):
            if i.samples[0].project.udf.get('Project type') == "Diagnostics":
                routables += [sample.artifact for sample in i.samples]
    if routables:
        workflows = lims.get_workflows()
        match_workflows = [] # Contains version, then workflow object
        for w in workflows:
            # This will do a GET for each workflow in the system. Performance is bad.
            m = re.match(r"processing of hts-data diag (\d)\.(\d)", w.name, re.IGNORECASE)
            if w.status == "ACTIVE" and m:
                match_workflows.append((int(m.group(1)), int(m.group(2)), w))
        workflow = sorted(match_workflows)[-1]
        lims.route_analytes(routables, workflow[2])

if __name__ == "__main__":
    main(sys.argv[1])

