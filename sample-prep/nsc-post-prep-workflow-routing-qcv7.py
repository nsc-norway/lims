# Assign analytes to the right workflow stage for library QC, based on which prep was
# used.
import sys
import re
from collections import defaultdict
from genologics.lims import *
from genologics import config

QC_WORKFLOW = "NSC QC 7.1"
STAGE_MAPPING = {
        'NSC_16S': 'Quant-iT 16S libraries'
        }

def die(*message):
    print(*message)
    sys.exit(1)


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    analytes = process.all_inputs(unique=True, resolve=True)

    stage_analytes = defaultdict(list)
    # Identify workflow for each of the samples
    for analyte in analytes:
        sample_prep_used = analyte.samples[0].udf.get('Sample prep NSC')
        # Using 0 as a placeholder for default stage = start of WF
        stage = STAGE_MAPPING.get(sample_prep_used, 0)
        stage_analytes[stage].append(analyte)

    # Load all workflows in the system
    try:
        workflow = lims.get_workflows(name=QC_WORKFLOW)[0]
    except IndexError:
        die("No workflow with name '{}' found.".format(QC_WORKFLOW))
    if workflow.status != "ACTIVE":
        die("Workflow {} status is {}, needs to be ACTIVE.".format(
            QC_WORKFLOW, workflow.status
            ))

    for stagename, analytes in stage_analytes.items():
        if stagename == 0:
            lims.route_analytes(analytes, workflow)
        else:
            try:
                stage = next(stage for stage in workflow.stages if stage.name == stagename)
            except StopIteration:
                die("The stage name {} is unknown.".format(stagename))
            lims.route_analytes(analytes, stage)


if __name__ == "__main__":
    main(*sys.argv[1:])

