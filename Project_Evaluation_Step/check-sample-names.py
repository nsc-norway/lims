# Script to populate fields in process for Project Evaluation workflow.

import sys
import re
import requests
from genologics.lims import *
from genologics import config

import settings


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    inputs = process.all_inputs(resolve=True)
    samples = lims.get_batch(input.samples[0] for input in inputs)

    invalid_chars = set()
    invalid_names = []
    names = []
    for sample in samples:
        sample_invalid_chars = re.sub(r"[a-zA-Z0-9-]", "", sample.name)
        names.append(sample.name)
        if sample_invalid_chars:
            invalid_chars.update(sample_invalid_chars)
            invalid_names.append(sample.name)

    if invalid_names:
        print "The following sample(s) have unsupported characters (" +\
                ", ".join("'" + c + "'" for c in invalid_chars) + \
                ") in their sample names, please correct using Modify Samples: ",\
                ", ".join(invalid_names), "."
        sys.exit(1)
    if len(set(names)) < len(names):
        for name in set(names):
            names.remove(name)

        print "Duplicate sample names detected:", ", ".join(names), "."
        sys.exit(1)


if len(sys.argv) == 2:
    main(sys.argv[1])
else:
    print "use: python check-sample-names.py PROCESS_ID"
    sys.exit(1)

