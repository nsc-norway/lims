# Assign analytes to the right workflow for library QC, based on which prep was
# used.
import sys
import re
from collections import defaultdict
from genologics.lims import *
from genologics import config

DEFAULT_WORKFLOW = "NSC QC"
WORKFLOW_MAPPING = {
        'NSC_16S': 'NSC 16S'
        }


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    analytes = process.all_inputs(unique=True, resolve=True)

    workflow_analytes = defaultdict(list)
    # Identify workflow for each of the samples
    for analyte in analytes:
        sample_prep_used = analyte.samples[0].udf.get('Sample prep NSC')
        workflow = WORKFLOW_MAPPING.get(sample_prep_used, DEFAULT_WORKFLOW)
        workflow_analytes[workflow].append(analyte)

    # Load all workflows in the system
    workflow_data = lims.get_workflows(add_info=True)

    # Look up each workflow name in the list of workflows, and assign it if available
    for workflow_prefix, analytes in workflow_analytes.items():
        for workflow, info in zip(*workflow_data):
            if info['status'] == "ACTIVE" and info['name'].startswith(workflow_prefix):
                lims.route_analytes(analytes, workflow)
                break
        else:
            print (("Error: Unknown workflow '{}' for samples ".format(workflow_prefix) +
                    ", ".join(analyte.name for analyte in analytes) +
                    "."))
            sys.exit(1)

if __name__ == "__main__":
    main(*sys.argv[1:])

