# Assign analytes of a given process to a workflow specified as a Artifact UDF
# The value can be a prefix of the workflow name (e.g. excluding the version number)

# Analytes can be either inputs or outputs. It used to be just outputs, but the 
# script was extended to fall back on inputs if there are no Analyte outputs on
# the process.

from __future__ import print_function
import sys
import re
from collections import defaultdict
from genologics.lims import *
from genologics import config

def main(process_id, workflow_udf, prefix=""):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    use_outputs = any(output.type == 'Analyte' for output in process.all_outputs(unique=True, resolve=True))
    if use_outputs:
        analytes = process.all_outputs(unique=True)
    else: # Use inputs
        analytes = process.all_inputs(unique=True, resolve=True)

    workflow_analytes = defaultdict(list)
    # Identify workflow for each of the samples
    for output in analytes:
        try:
            workflow = prefix.decode('utf-8') + output.udf[workflow_udf]
        except KeyError:
            print("Error: workflow name (" +str(workflow_udf)+u") not specified for sample " + output.name)
            sys.exit(1)
        workflow_analytes[workflow].append(output)

    # Load all workflows in the system
    workflow_data = lims.get_workflows(add_info=True)

    # Look up each workflow name in the list of workflows, and assign it if available
    for workflow_prefix, analytes in workflow_analytes.items():
        for workflow, info in zip(*workflow_data):
            if info['status'] == "ACTIVE" and info['name'].startswith(workflow_prefix):
                lims.route_analytes(analytes, workflow)
                break
        else:
            print ((u"Error: Unknown workflow '" + unicode(workflow_prefix) + u"' for samples "+
                    u", ".join(output.name for output in analytes) +
                    u".").encode('utf-8'))
            sys.exit(1)

if __name__ == "__main__":
    main(*sys.argv[1:])

