import sys
import re
import requests
from genologics.lims import *
from genologics import config

import settings


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    # Get the first sample and project
    sample = process.all_inputs()[0].samples[0]
    project = sample.project
    proj_id = None

    # Set Project UDFs
    any_set = False
    for udfname in settings.project_fields:
        try:
            process.udf[udfname] = project.udf[udfname]
            any_set = True
        except KeyError:
            pass

    # Set Sample UDFs
    for dest_udf, src_udf in settings.sample_fields:
        try:
            process.udf[dest_udf] = sample.udf[src_udf]
            any_set = True
        except KeyError:
            pass

    if any_set:
        try:
            process.put()
        except requests.exceptions.HTTPError:
            # Ignore errors when setting values on process.
            # Will fail if it's a sample with some missing UDFs
            pass


if len(sys.argv) == 2:
    main(sys.argv[1])
else:
    print "use: python copy-fields-to-process.py PROCESS_ID"
    sys.exit(1)

