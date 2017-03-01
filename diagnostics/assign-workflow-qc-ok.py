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
    lims.get_batch(process.all_inputs(unique=True) + process.all_outputs(unique=True))
    lims.get_batch(output.samples[0] for output in process.all_outputs(unique=True))
    routables = []
    for i, o in process.input_output_maps:
        if o['output-generation-type'] == "PerReagentLabel":
            if i['uri'].qc_flag == "PASSED":
                if o['uri'].samples[0].project.udf.get('Project type') == "Diagnostics":
                    routables.append(o['uri'].samples[0].artifact)

    if routables:
        lims.route_analytes(routables, workflow)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

