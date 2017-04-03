# coding: utf-8
# Copy the value of a UDF on the previous step to the current one.

import sys
import datetime
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    inputs = process.all_inputs()
    prev_processes = sorted([p 
            for p in lims.get_processes(inputartifactlimsid=[i.id for i in inputs])
            if p.type_name.startswith("Resultatvurdering_diag")],
            key=lambda p: int(p.id.split("-")[1])
            )

    if len(prev_processes) == 0:
        print("Fant ingen resultatvurdering")
        sys.exit(1)
    for other_process in reversed(prev_processes):
        process.udf['Dato for kontroll av resultatvurdering:'] = datetime.date.today()
        process.udf['Dato for utfort resultatvurdering:'] = other_process.udf['Dato resultatvurdering ferdig']
        process.udf['Resultatvurdering utfort av:'] = other_process.udf['Signaturkode']
        process.put()
        break

if __name__ == "__main__":
    main(process_id=sys.argv[1])

