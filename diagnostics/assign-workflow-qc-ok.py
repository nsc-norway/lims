# Assign sequenced diagnostics samples to interpretation workflow

import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    # Get inputs of demultiplexing step (process)
    inputs = list(set(i['uri'].stateless for i, o in process.input_output_maps
                    if o['output-generation-type'] == "PerReagentLabel"))
    
    diag_inputs = []
    for inp in inputs:
        # Check if the first sample that's not a control sample has Diag project
        for sample in inp.samples:
            if sample.project:
                if sample.project.udf.get('Project type') == "Diagnostics":
                    diag_inputs.append(inp)
                break

    if diag_inputs:
        # Find MiSeq Run / NextSeq Run / NovaSeq Data QC
        qc_proc = None
        for qc_proc_cand in lims.get_processes(inputartifactlimsid=[a.id for a in diag_inputs]):
            # Get the first output with 'PerInput'
            for i, o in qc_proc_cand.input_output_maps:
                if o['output-generation-type'] == 'PerInput':
                    if o['uri'].stateless.qc_flag != "UNKNOWN":
                        # This is a QC process, good enough
                        qc_proc = qc_proc_cand
                    break
            if qc_proc:
                break

        # Find the artifacts to route (put in dict to de-duplicate)
        routables = {}
        if qc_proc:
            for inp in diag_inputs:
                # Find the QC state of this lane
                for i, o in qc_proc.input_output_maps:
                    if o['output-generation-type'] == 'PerInput' and i['limsid'] == inp.id:
                        if o['uri'].stateless.qc_flag == 'PASSED':
                            for sam in lims.get_batch(inp.samples):
                                routables[sam.artifact.id] = sam.artifact

        if routables:
            workflows = lims.get_workflows()
            match_workflows = [] # Contains version, then workflow object
            for w in workflows:
                # This will do a GET for each workflow in the system. Performance is bad.
                m = re.match(r"processing of hts-data diag (\d)\.(\d)", w.name, re.IGNORECASE)
                if w.status == "ACTIVE" and m:
                    match_workflows.append((int(m.group(1)), int(m.group(2)), w))
            workflow = sorted(match_workflows)[-1]
            lims.route_analytes(routables.values(), workflow[2])

if __name__ == "__main__":
    main(sys.argv[1])

