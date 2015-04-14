import sys
from genologics.lims import *
from genologics import config


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    
    projects = {}
    for ana in process.all_inputs():
        project = ana.samples[0].project
        projects[project.id] = project

    for project in projects:
        project.udf['Project Type'] = process.udf['Project Type']
        project.put()


if len(sys.argv) == 2:
    main(sys.argv[1])
else:
    print "use: python set-sample-udfs.py PROCESS_ID"
    sys.exit(1)


