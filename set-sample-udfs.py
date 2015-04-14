import sys
from genologics.lims import *
from genologics import config


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    
    for analyte in process.all_inputs(unique=True):
        sample = analyte.samples[0]
        
        for udfname, udfval in process.udf.items():
            sample.udf['NSC ' + udfname] = udfval
            sample.put()


if len(sys.argv) == 2:
    main(sys.argv[1])
else:
    print "use: python set-sample-udfs.py PROCESS_ID"
    sys.exit(1)


