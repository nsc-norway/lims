import sys
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    inputs = process.all_inputs(unique=True)
    for input in inputs:
        pass



main(sys.argv[1])

