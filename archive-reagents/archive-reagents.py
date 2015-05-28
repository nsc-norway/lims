import sys
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)

    

if __name__ == "__main__":
    main(sys.argv[0])
