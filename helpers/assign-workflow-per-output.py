# Assign outputs of a given process to a workflow specified as a Artifact UDF
from __future__ import print_function
import sys
import re
from collections import defaultdict
from genologics.lims import *
from genologics import config

def main(process_id, workflow_udf):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    outputs = process.all_outputs(unique=True, resolve=True)
    workflow_outputs = defaultdict(list)
    for output in outputs:
        if output.type == "Analyte" and not output.control_type:
            try:
                workflow = output.udf[workflow_udf]
            except KeyError:
                print("Error: workflow name (" +str(workflow_udf)+") not specified for sample ", output.name)
                sys.exit(1)
            workflow_outputs[workflow].append(output)

    for workflow_name, outputs in workflow_outputs.items():
        workflows = lims.get_workflows(name=workflow_name)
        if workflows:
            workflow = workflows[0]
        else:
            print ("Error: Unknown workflow '" + str(workflow_name) + "' for samples "+
                    ", ".join(output.name for output in outputs) +
                    ".")
            sys.exit(1)
        lims.route_analytes(process.all_inputs(unique=True), workflow)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

