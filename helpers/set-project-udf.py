import sys
from genologics.lims import *
from genologics import config

# Project UDF set script

# Sets UDF on the project of all the output analytes to the value provided on the
# command line.

# This script currently only handles string type UDF! We already have bool (and
# though that was enough forever).

def main(process_id, key_value_pairs):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    inputs = lims.get_batch(process.all_inputs(unique=True))
    samples = sum((input.samples for input in inputs), [])
    lims.get_batch(samples)
    projects = set(sample.project for sample in samples if sample.project)
    for project in projects:
        for key,value in zip(key_value_pairs[::2], key_value_pairs[1::2]):
            project.udf[key] = value
        project.put()

main(sys.argv[1], sys.argv[2:])

