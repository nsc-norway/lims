import sys
from genologics.lims import *
from genologics import config

def main(process_id, workflow_name, stage_number):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    workflow_data = lims.get_workflows(name=workflow_name)
    if not workflow_data:
        print("No such workflow '{0}'".format(workflow_name))
        sys.exit(1)
    analytes = process.all_inputs(unique=True)
    stage = workflow_data[0].stages[int(stage_number)]
    lims.route_analytes(analytes, stage)
    print ("{0} samples successfully queued at '{1}'.".format(len(analytes), stage.name))

if __name__ == "__main__":
    main(*sys.argv[1:])

