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
    input_measurement = []
    for i, o in process.input_output_maps:
        if o and o['output-type'] == 'ResultFile' and o['output-generation-type'] == 'PerInput':
            input = i['uri']
            measurement = o['uri']
            input_measurement.append((input, measurement))

    lims.get_batch([item for im in input_measurement for item in im])

    for input, measurement in input_measurement:
        try:
            for field in fields:
                input.udf[field] = measurement.udf[field]
        except KeyError:
            print "Missing value for", field, "on sample", input.name.encode('utf-8'), "."
            sys.exit(1)

    lims.put_batch([input for input, measurement in input_measurement])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])

