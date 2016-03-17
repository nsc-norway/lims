# Check that container name is not the default (= LIMSID)

import sys
from genologics.lims import *
from genologics import config
import re

def main(process_id, operation):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    # analytes() returns tuples ('Output', [Analyte, ...]).
    ios = process.input_output_maps

    lims.get_batch(a['uri'] for io in ios for a in io if io[1]['output-type'] == "Analyte")

    updated = []
    for i,o in ios:
        if o['output-type'] == "Analyte":
            a = o['uri']
            prefix = "%3.1f nM | " % (i['uri'].udf.get('Molarity', 0.0))
            if operation == "add":
                if not a.name.startswith(prefix):
                    a.name = prefix + a.name
                    updated.append(a)
            elif operation == "remove":
                if a.name.startswith(prefix):
                    a.name = a.name[len(prefix):]
                    updated.append(a)

    lims.put_batch(updated)


main(sys.argv[1], sys.argv[2])

