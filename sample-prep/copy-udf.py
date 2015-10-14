import sys
from genologics import config
from genologics.lims import *

def main(process_id, udfname):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    ios = []
    for i, o in process.input_output_maps:
        if o['output-generation-type'] == 'PerInput' and o['output-type'] == 'Analyte':
            ios.append(i['uri'], o['uri'])

    lims.get_batch(el for io in ios for el in io)
    missing = []
    for i, o in ios:
        try:
            o.udf[udfname] = i.udf[udfname]
        except KeyError:
            missing.append(i)

    lims.put_batch(io[1] for io in ios)

main(*sys.argv[1:4])

