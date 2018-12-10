import sys
from genologics.lims import *
from genologics import config

# Project UDF set script

# Sets UDF on the project of all the output analytes to the value provided on the
# command line.

# This script only handles "bool" type UDF! Very limited, but probably the only 
# project UDF we will ever need.

def main(process_id, key_value_pairs):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    inputs = lims.get_batch(process.all_inputs(unique=True))
    samples = sum((input.samples for input in inputs), [])
    lims.get_batch(samples)
    projects = set(sample.project for sample in samples if sample.project)
    for project in projects:
        for key,value in zip(key_value_pairs[::2], key_value_pairs[1::2]):
            project.udf[key] = bool(value)
            project.put()

main(sys.argv[1], sys.argv[2:])

