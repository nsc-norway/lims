import sys
from genologics.lims import *
from genologics import config

import checks


project_fields = [
    "Contact name",
    "String",
    "Contact institution",
    "Contact address",
    "Contact email",
    "Contact telephone",
    "Billing contact person",
    "Billing institution",
    "Billing address",
    "Billing email",
    "Billing telephone",
    "Purchase order number",
    "Kontostreng (Internal orders only)",
    "Delivery method"
    ]



email_fields = ['Email', 'Billing email']

def check(udfname, udfvalue):
    """Check if provided string is valid"""

    if udfname in email_fields:
        if not checks.is_valid_email(udfvalue):
            print "Text in", udfname, "is not a valid e-mail address."
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

    # Set UDFs
    for udfname in project_fields:
        udfvalue = process.udf[udfname]
        if not check(udfname, udfvalue):
            sys.exit(1)
        project.udf[udfname] = udfvalue
    project.put()


if len(sys.argv) == 2:
    main(sys.argv[1])
else:
    print "use: python set-sample-udfs.py PROCESS_ID"
    sys.exit(1)

