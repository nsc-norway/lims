# Use the user-provided concentration measurement in an aggregate QC step

import sys
import re
from genologics.lims import *
from genologics import config


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    for i in process.all_inputs(unique=True):
        user_conc = i.samples[0].udf['Sample Conc.']
        i.udf['Concentration'] = user_conc
        i.put()


if len(sys.argv) == 2:
    main(sys.argv[1])
else:
    print "use: python set-user-concentration.py PROCESS_ID"
    sys.exit(1)

