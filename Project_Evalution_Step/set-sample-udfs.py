# For the project evaluation workflow.
# Copies UDFs from a process to the Sample objects associated with the 
# inputs of that process, and the Project associated with those samples.

import sys
import re
from genologics.lims import *
from genologics import config

import settings


def check(udfname, udfvalue):
    """Check if provided string is valid"""

    if udfname in settings.email_fields:
        if re.search(r"[A-Z]", udfvalue):
            print "Capital letters not allowed in email addresses, in ", udfname, "."
            return False

    return True


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    # Check that all samples are from the same project
    proj_id = None
    for ana in process.all_inputs():
        project = ana.samples[0].project
        if not proj_id:
            proj_id = project.id
        if proj_id != project.id:
            print "Samples from more than one project are not allowed"
            sys.exit(1)

    # Set Project UDFs
    for udfname in settings.project_fields:
        try:
            udfvalue = process.udf[udfname]
        except KeyError:
            continue

        if udfname in settings.email_fields:
            if not re.match(r".*@.+\..+$", udfvalue):
                print "Text in", udfname, "is not a valid e-mail address."
                sys.exit(1)
            udfvalue = udfvalue.lower()

        project.udf[udfname] = udfvalue
    project.put()

    # Set Sample UDFs
    #for ana in process.all_inputs(unique=True):
    #    sample = ana.samples[0]
    #    for src_udf, dest_udf in settings.sample_fields:
    #        try:
    #            sample.udf[dest_udf] = process.udf[src_udf]
    #        except KeyError:
    #            pass
    #    sample.put()

if len(sys.argv) == 2:
    main(sys.argv[1])
else:
    print "use: python set-sample-udfs.py PROCESS_ID"
    sys.exit(1)

