# Rename each tube with information about original plate and position

import sys
from collections import defaultdict
import re
import requests
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    analyte_ios = [(i, o) for i,o in process.input_output_maps if o['output-generation-type'] == "PerInput"]
    all_analytes = lims.get_batch(a['uri'] for i, o in analyte_ios for a in [i,o])
    lims.get_batch(a.location[0] for a in all_analytes)

    replicate_index = defaultdict(int)
    
    for i, o in analyte_ios:
        out_tube_name = i['uri'].location[0].name + "_" + i['uri'].location[1]
        replicate_index[out_tube_name] += 1
        out_tube_name += "_" + str(replicate_index[out_tube_name]).zfill(2)
        o['uri'].location[0].name = out_tube_name

    output_containers = [o['uri'].location[0] for i, o in analyte_ios]
    failures = []
    try:
        lims.put_batch(output_containers)
    except requests.exceptions.HTTPError:
        print "Tube rename error!"
        sys.exit(1)


main(sys.argv[1])

