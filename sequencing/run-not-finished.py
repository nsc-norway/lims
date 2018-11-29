# Run not finished 

import sys
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
process = Process(lims, id=sys.argv[1])
process.get()
process.udf['Finish Date'] = None
process.put()

