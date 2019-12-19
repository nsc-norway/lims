# Set Experiment Name UDF to the project name of the first sample
import sys
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    process.udf['Experiment Name'] = process.all_inputs()[0].samples[0].project.name
    process.udf['MiSeq instrument'] = '-- Choose one --' # Required field must be set
    process.put()

main(sys.argv[1])

