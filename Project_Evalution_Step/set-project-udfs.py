# For the project evaluation workflow.
# Copies UDFs from a process to the Sample objects associated with the 
# inputs of that process, and the Project associated with those samples.

import sys
import re
from genologics.lims import *
from genologics import config

import settings



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
        
        single_line_field = settings.multiline_to_single_line.get(udfname)
        if single_line_field:
            project.udf[single_line_field] = " ".join(udfvalue.splitlines())
        
    project.put()

if len(sys.argv) == 2:
    main(sys.argv[1])
else:
    print "use: python set-sample-udfs.py PROCESS_ID"
    sys.exit(1)

