import sys
from genologics.lims import *
from genologics import config

import checks


project_fields = [
        "Project Type",
        "Application",
        "Sequencing method",
        "Sequencing instrument requested",
        "Read length requested",
        "Sample prep requested",
        "Desired insert size",
        "Delivery method",
        "Reference genome",
        "Contact person",
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
        "Funded by Norsk Forskningsradet",
        "Kontostreng (Internal orders only)",
]

sample_fields = [
        "Sample type",
        "Sample buffer",
        "Method used to determine concentration",
        "Method used to purify DNA/RNA"
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

    # Set Project UDFs
    for udfname in project_fields:
        try:
            udfvalue = process.udf[udfname]
        except KeyError:
            continue

        if not check(udfname, udfvalue):
            sys.exit(1)
        project.udf[udfname] = udfvalue
    project.put()

    # Set Sample UDFs
    for ana in process.all_inputs(unique=True):
        sample = ana.sample[0]
        for udfname in sample_fields:
            sample.udf['NSC ' + udfname] = ana.udf[udfname]
        sample.put()

if len(sys.argv) == 2:
    main(sys.argv[1])
else:
    print "use: python set-sample-udfs.py PROCESS_ID"
    sys.exit(1)

