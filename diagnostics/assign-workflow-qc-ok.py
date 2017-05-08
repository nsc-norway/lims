# Assign sequenced diagnostics samples to interpretation workflow

import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    inputs = process.all_inputs(unique=True)
    lims.get_batch(inputs)
    lims.get_batch(sample for input in inputs for sample in input.samples)
    routables = []
    for i, o in process.input_output_maps:
        if o['output-generation-type'] == "PerReagentLabel":
            if i['uri'].stateless.qc_flag == "PASSED":
                if i['uri'].samples[0].project.udf.get('Project type') == "Diagnostics":
                    routables += [sample.artifact for sample in i['uri'].samples]

    if routables:
        workflows = lims.get_workflows()
        match_workflows = [] # Contains version, then workflow object
        for w in workflows:
            # This will do a GET for each workflow in the system. Performance is bad.
            m = re.match(r"Tolkning av HTS-data diag (\d)\.(\d)", w.name, re.IGNORECASE)
            if w.status == "ACTIVE" and m:
                match_workflows.append((int(m.group(1)), int(m.group(2)), w))
        workflow = sorted(match_workflows)[-1]
        lims.route_analytes(routables, workflow)

if __name__ == "__main__":
    main(sys.argv[1])

