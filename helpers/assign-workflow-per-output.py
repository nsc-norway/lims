# Assign outputs of a given process to a workflow specified as a Artifact UDF
# The value can be a prefix of the workflow name (e.g. excluding the version number)

from __future__ import print_function
import sys
import re
from collections import defaultdict
from genologics.lims import *
from genologics import config

def main(process_id, workflow_udf, prefix=""):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    outputs = process.all_outputs(unique=True, resolve=True)
    workflow_outputs = defaultdict(list)
    # Identify workflow for each of the samples
    for output in outputs:
        if output.type == "Analyte" and not output.control_type:
            try:
                workflow = prefix.decode('utf-8') + output.udf[workflow_udf]
            except KeyError:
                print("Error: workflow name (" +str(workflow_udf)+u") not specified for sample " + output.name)
                sys.exit(1)
            workflow_outputs[workflow].append(output)

    # Load all workflows in the system
    workflow_data = lims.get_workflows(add_info=True)

    # Look up each workflow name in the list of workflows, and assign it if available
    for workflow_prefix, outputs in workflow_outputs.items():
        for workflow, info in zip(*workflow_data):
            if info['status'] == "ACTIVE" and info['name'].startswith(workflow_prefix):
                lims.route_analytes(outputs, workflow)
                break
        else:
            print ((u"Error: Unknown workflow '" + unicode(workflow_prefix) + u"' for samples "+
                    u", ".join(output.name for output in outputs) +
                    u".").encode('utf-8'))
            sys.exit(1)

if __name__ == "__main__":
    main(*sys.argv[1:])

