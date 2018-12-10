# Stores the difference between two numbers give on the command line

# python subtractor.py PROCESS_ID UDF_NAME A B
# Symbolically, the result is to set:
# [UDF_NAME] <- A - B

import sys
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
process = Process(lims, id=sys.argv[1])
process.get()
process.udf[sys.argv[2]] = float(sys.argv[3]) - float(sys.argv[4])
process.put()

