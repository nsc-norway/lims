import sys
from genologics.lims import *
from genologics import config

# Custom UDFs for analyte

FILE_LIMS_NAME = "sample_grid.csv"

def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    outputs = {}
    for io in process.input_output_maps:
        out = io[1]
        if out['output-generation-type'] == 'PerInput':
            outputs[out['uri'].location[1]] = out['uri']

    result_rows = []
    for row in ['A','B','C','D','E','F','G','H']:
        row_cells = []
        for col in xrange(1,13):
            try:
                row_cells.append(outputs["{0}:{1}".format(row, col)].id)
            except KeyError:
                row_cells.append('""')

        result_rows.append(",".join(row_cells))

    result = "\n".join(result_rows)
    output_artifact = Artifact(lims, id=output_file_id)
    assert(output_artifact.name == FILE_LIMS_NAME)
    pf = ProtoFile(lims, output_artifact, FILE_LIMS_NAME)
    pf = lims.glsstorage(pf)
    f = pf.post()
    f.upload(result)

main(sys.argv[1], sys.argv[2])

