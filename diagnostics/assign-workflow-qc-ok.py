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
        lims.route_analytes(routables, workflow)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

