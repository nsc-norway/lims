import sys
import re
from genologics.lims import *
from genologics import config

# Use:
# python run-parameters.py [-p] RUN_ID
# Use -p to change the output into pipe separated key/values

def main(run_id, parsable):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    for instrument, ptype in [
            ("hiseq", "Illumina Sequencing (Illumina SBS) 5.0"),
            ("miseq", "MiSeq Run (MiSeq) 5.0"),
            ("nextseq", "NextSeq Run (NextSeq) 1.0"),
            ]:
        processes = lims.get_processes(type=ptype, udf={'Run ID': run_id})
        if len(processes) == 1:
            break
        elif len(processes) > 1:
            print "Multiple sequencing processes exist for", run_id, ", don't know which one to report."
            sys.exit(1)
    else: # if not break 
        print "Run", run_id, "not found in LIMS."
        sys.exit(1)

    for process in processes: # There is just one
        data = [("Instrument", instrument)] + list(process.udf.items())
        for udfname, udfval in data:
            if parsable:
                print udfname + "|" + str(udfval)
            else:
                print "%-25s %s" % (udfname, udfval)

try:
    run_id = next(x for x in sys.argv[1:] if x[0] != "-")
except StopIteration:
    print "use: python run-parameters.py [-p] RUN_ID"
    sys.exit(1)
main(run_id, '-p' in sys.argv)

