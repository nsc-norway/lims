from genologics.lims import *
from genologics import config
import sys

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} PROCESS_ID")
    sys.exit(1)

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

process = Process(lims, id=sys.argv[1])

required_fields = ['Spike-in %', 'Spike-in final molarity (nM)']
projects_to_put = set()
for input in process.all_inputs(unique=True):
    for field in required_fields:
        if field not in input.udf:
            print("Error: '{}' is required, but not specified for pool '{}'. Please go back to Record Details and set it.".format(field, input.name))
            sys.exit(1)
    for sample in lims.get_batch(input.samples):
        projects_to_put.add(sample.project)

for project in projects_to_put:
    project.udf['Project type'] = "PGT"
    project.udf['Delivery method'] = "OUS network filsluse"
    project.udf['Sample type'] = "gDNA"
    project.put()

