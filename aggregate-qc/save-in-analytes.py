import sys
from genologics.lims import *
from genologics import config

# Copies specified UDFs from the ResultFile outputs representing the
# measurement results, to the analyte inputs of the process.

# This is like a mini Aggregate QC, but in the same step as the measurement.

# Use: python save-in-analytes.py PROCESS-ID {FIELD-NAME}
# (can give multiple field names)

def main(process_id, fields):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    for i, o in process.input_output_maps:
        if o and o['output-type'] == 'ResultFile' and o['output-generation-type'] == 'PerInput':
            input = i['uri']
            measurement = o['uri']
            for field in fields:
                input.get()
                input.udf[field] = measurement.udf[field]
                input.put()

main(sys.argv[1], sys.argv[2:])

