# Note: Python 3 source code, run under SCL.
# -*- coding: utf-8 -*-

# This script was adapted from worksheet_generator.py


from genologics.lims import *
from genologics import config
import sys
import xlwt

# Script usage: generate_worksheet.py <PROCESS_ID> <OUTPUT_FILE_ID>

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
process = Process(lims, id=sys.argv[1])

wb = xlwt.Workbook()
ws = wb.add_sheet('Sheet1')

def sort_key(elem):
    input, output = elem
    container, well = output.location
    row, col = well.split(":")
    return (container, int(col), row)

headers = [
    "Sample_Number",
    "Labware",
    "Position_ID",
    "Volume_DNA",
    "Destination_Well_ID"
    ]

for i, header in enumerate(headers):
    ws.write(0, i, header)

i_os = process.input_output_maps
inputs_outputs = [(i['uri'], o['uri']) for i,o in i_os if o['output-generation-type'] == 'PerInput']
lims.get_batch([i for i,o in inputs_outputs] + [o for i,o in inputs_outputs])
lims.get_batch(i.samples[0] for i, o in inputs_outputs)
for row_index, (input, output) in enumerate(sorted(inputs_outputs, key=sort_key)):
    ws.write(row_index+1, 0, input.name)
    ws.write(row_index+1, 1, "Rack{}".format(1 + (row_index + 7) // 32))
    ws.write(row_index+1, 2, 1 + (row_index + 7) % 32 )
    try:
        conc = input.samples[0].udf['Sample conc. (ng/ul)']
    except KeyError:
        ws.write(row_index+1, column=3).value = "MISSING"
        continue
    if conc >= 9 and conc <= 180:
        ws.write(row_index+1, 3, 2)
    else:
        # Compute 3 ng/uL in 45 uL total volume
        sample_vol = (3 * 45) / conc
        ws.write(row_index+1, 3, sample_vol)
    ws.write(row_index+1, 4, output.location[1].replace(":", ""))

wb.save(sys.argv[2] + '-hamilton.xls')

