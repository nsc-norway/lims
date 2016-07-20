# Copy the value of a UDF on the previous step to the current one.

import sys
import datetime
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    inputs = process.all_inputs()
    prev_processes = lims.get_processes(inputartifactlimsid=[i.id for i in inputs], type="Resultatvurdering_diag")
    if len(prev_processes) != 1:
        print("Forventet en enkelt resultatvurdering, fant " + str(len(prev_processes)))
        sys.exit(1)
    for other_process in reversed(prev_processes):
        process.udf['Dato kontroll av resultatvurdering ferdig'] = datetime.date.today()
        process.udf['Signaturkode eller EGG'] = other_process.udf['Signaturkode']
        process.put()
        break

if __name__ == "__main__":
    main(process_id=sys.argv[1])

