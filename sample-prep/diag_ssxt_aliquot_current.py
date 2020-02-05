import sys
import xlwt
from genologics.lims import *
from genologics import config

# Computation for SSXT Aliquote DNA step at the beginning of Target Enrichment protocol
# xls file for hamilton robot
# -> The calculation should be exactly the same as in aliquot-volume.py.

# Second version of file, using a different UDF for concentration. The step config was not
# created with indirection through processtype/ dir, so we have to leave the original
# script (without _current suffix) as it is.

MAX_VOL = 30

def sort_key(elem):
    output = elem[1]
    container, well = output.location
    row, col = well.split(":")
    return (container.id, int(col), row)


def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    inputs = []
    outputs = []
    for i,o in process.input_output_maps:
        output = o['uri']
        if o and o['output-type'] == 'Analyte' and o['output-generation-type'] == 'PerInput':
            input = i['uri']
            inputs.append(input)
            outputs.append(output)

    book = xlwt.Workbook()
    sheet1 = book.add_sheet('Sheet1')
    sheet1.write(0, 0, 'SamplePlate')
    sheet1.write(0, 1, 'Volume')

    lims.get_batch(inputs + outputs)
    lims.get_batch(input.samples[0] for sample in inputs)

    i_os = zip(inputs, outputs)
    for i, (input, output) in enumerate(sorted(i_os, key=sort_key), 1):
        quantity = process.udf['DNA per sample (ng)']
        input_conc = input.udf['Concentration (ng/ul)']
        if input_conc <= 0:
            volume = MAX_VOL
        else: 
            volume = min(quantity * 1.0 / input_conc, MAX_VOL)
        sheet1.write(i, 0, input.location[1][:1] + input.location[1][2:])
        sheet1.write(i, 1, round(volume, 1))

    book.save(output_file_id + "-AliquotFile_Hamilton.xls")



main(*sys.argv[1:3])

