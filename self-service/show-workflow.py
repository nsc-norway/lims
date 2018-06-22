import sys
from genologics.lims import *
from genologics import config

def main(process_id, workflow_name):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    workflow_data = lims.get_workflows(name=workflow_name)
    if not workflow_data:
        print("No such workflow '{0}'".format(workflow_name))
        sys.exit(1)
    the_list = []
    for i, stage in enumerate(workflow_data[0].stages):
        the_list.append("{0:02}. {1}".format(i, stage.name))
    process.udf['Information'] = "\n".join(the_list)
    process.put()

if __name__ == "__main__":
    main(*sys.argv[1:])

