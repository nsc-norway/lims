import sys
from genologics.lims import *
from genologics import config

def main(process_id, output_file_path):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    outputs = {}
    # TODO!


main(sys.argv[1], sys.argv[2])

