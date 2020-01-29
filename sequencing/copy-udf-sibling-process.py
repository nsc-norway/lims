import sys
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
process = Process(lims, id=sys.argv[1])
input = next(iter(process.all_inputs(unique=True)))
procs = lims.get_processes(inputartifactlimsid=input.id)
for pp in procs:
    if pp.id != process.id:
        for udfname in sys.argv[2:]:
            val = pp.udf.get(udfname)
            if val:
                process.udf[udfname] = val
process.put()


