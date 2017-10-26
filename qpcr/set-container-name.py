import sys
from genologics.lims import *
from genologics import config
from collections import defaultdict
import re

def main(process_id, resultfile_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    outfile = Artifact(lims, id=resultfile_id)
    try:
        data = outfile.files[0].download()
        experiment_name = re.match(r"Experiment:\s(\S+)\s", data).group(1)
        container = process.all_outputs()[0].location[0]
        container.name = experiment_name
        container.put()
    except Exception as e:
        print("Unable to set the output container name: " + str(e))
        sys.exit(1)

main(*sys.argv[1:3])

