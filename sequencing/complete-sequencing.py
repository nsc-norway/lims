# Mark as completed in LIMS 

import sys
from datetime import date
from genologics.lims import *
from genologics import config

# Container UDFs to track flow cells
RECENTLY_COMPLETED_UDF = "Recently completed"
PROCESSED_DATE_UDF = "Processing completed date"

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    
    inputs = process.all_inputs(unique=True)
    flowcells = set(i.location[0] for i in inputs)
    if len(flowcells) == 1:
        fc = next(iter(flowcells))
        fc.get()
        # Tracking UDF for "overview" page
        fc.udf[RECENTLY_COMPLETED_UDF] = True
        fc.udf[PROCESSED_DATE_UDF] = date.today()
        fc.put()

main(sys.argv[1])

