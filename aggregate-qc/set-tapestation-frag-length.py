# Set the tapestation fragment length

import sys
import re
from genologics.lims import *
from genologics import config


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    # Search for sibling processes
    sprocs = lims.get_processes(
            inputartifactlimsid=[i.id for i in process.all_inputs(unique=True)]
            )
    
    date_process = sorted([(sproc.date_run, sproc) for sproc in sprocs], reverse=True)
    for input in process.all_inputs(unique=True):
        for date, sproc in date_process:
            if "Tapestation" in sproc.type.name and input in sproc.all_inputs():
                resultfiles = sproc.outputs_per_input(input.id, ResultFile=True)
                if len(resultfiles) == 1:
                    resultfile = resultfiles[0]
                    try:
                        input.udf['Fragment Length'] = resultfile.udf['Region 1 Average Size - bp']
                        print 'Updated sample with ID', input.id
                        input.put()
                        break # Skip to next input
                    except KeyError, e:
                        print 'Missing "Region 1 Average Size - bp" on result file.'


if len(sys.argv) == 2:
    main(sys.argv[1])
else:
    print "use: python",sys.argv[0],"PROCESS_ID"
    sys.exit(1)

