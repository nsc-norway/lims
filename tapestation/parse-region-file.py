import os
import sys
import csv
from genologics.lims import *
from genologics import config

EXPECT_COLUMNS = 8
FILE_LIMS_NAME = "Region csv file"

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    file_data = None
    for out in process.all_outputs():
        if out.name == FILE_LIMS_NAME:
            if len(out.files) > 0:
                file_data = out.files[0].download()

    if not file_data:
        print "No file to read"
        sys.exit(1)

    well_input = dict((i.location[1], i) for i in process.all_inputs())

    lines = file_data.splitlines()
    # Parse header row
    h = dict((cell, i) for cell, i in enumerate(lines[0].split(",")))

    for l in lines[1:]:
        cell = l.split(",")
        well = cell[h['WellId']]
        i = well_input[well[0] + ":" + well[1]]

        i.udf[''] = cell[h['']]
        #...
        i.put()


main(sys.argv[1])
