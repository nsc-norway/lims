import sys
from genologics.lims import *
from genologics import config
from collections import defaultdict
import re

def main(process_id, qpcrdatafile_id, result_artifact_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    qpcrresultfile = Artifact(lims, id=qpcrdatafile_id)
    resultartifact = Artifact(lims, id=result_artifact_id)
    try:
        data = qpcrresultfile.files[0].download()
        experiment_name = re.match(r"Experiment:\s(\S+)\s", data).group(1)
        container = resultartifact.location[0]
        container.name = experiment_name
        container.put()
    except Exception as e:
        print("Unable to set the output container name: " + str(e))
        sys.exit(1)

main(process_id=sys.argv[1], qpcrdatafile_id=sys.argv[2], result_artifact_id=sys.argv[3])

