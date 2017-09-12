# Note: Python 3 source code, run under SCL.

# -*- coding: utf-8 -*-

from openpyxl.styles import Border, Side, Alignment
from openpyxl import Workbook
import openpyxl
from genologics.lims import *
from genologics import config
import sys

# Script usage: generate_worksheet.py <PROCESS_ID> <OUTPUT_FILE_ID>

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
process = Process(lims, id=sys.argv[1])

wb = Workbook()
ws = wb.active

side_style = Side(border_style="thin")
border_style = Border(top=side_style, left=side_style, right=side_style, bottom=side_style)

def sort_key(elem):
    input, output = elem
    container, well = output.location
    row, col = well.split(":")
    return (container, int(col), row)

headers = [
    "Prøvenummer",
    "Arkivposisjon",
    "Konsentrasjon ng/µL",
    "Posisjon",
    "µL EB",
    "µL DNA",
    ]

for i, header in enumerate(headers, 1):
    cell = ws.cell(row=1, column=i)
    cell.value = header
    ws.column_dimensions[chr(ord('A')+i)].bestFit=True
    ws.column_dimensions[chr(ord('A')+i)].hidden=False
    for i in range(1, len(headers)+1):
        ws.cell(row=1, column=i).border = border_style

for i, width in enumerate([32, 12, 18, 8, 6, 8]):
    ws.column_dimensions[chr(ord('A')+i)].width = width

i_os = process.input_output_maps
inputs_outputs = [(i['uri'], o['uri']) for i,o in i_os if o['output-generation-type'] == 'PerInput']
lims.get_batch([i for i,o in inputs_outputs] + [o for i,o in inputs_outputs])
lims.get_batch(i.samples[0] for i, o in inputs_outputs)
for row_index, (input, output) in enumerate(sorted(inputs_outputs, key=sort_key), 2):
    for i in range(1, len(headers)+1):
        ws.cell(row=row_index, column=i).border = border_style
    ws.cell(row=row_index, column=1).value = input.name
    ws.cell(row=row_index, column=2).value = input.samples[0].udf.get('Archive position Diag', 'UKJENT')
    ws.cell(row=row_index, column=4).value = output.location[1].replace(":", "")
    try:
        conc = input.samples[0].udf['Sample conc. (ng/ul)']
    except KeyError:
        ws.cell(row=row_index, column=3).value = "UKJENT"
        continue
    ws.cell(row=row_index, column=3).value = conc
    for i in range(2, len(headers)+1):
        ws.cell(row=row_index, column=i).alignment = Alignment(horizontal="right")
    if conc >= 9 and conc <= 180:
        ws.cell(row=row_index, column=5).value = 43
        ws.cell(row=row_index, column=6).value = 2
    else:
        # Compute 3 ng/uL in 45 uL total volume
        if conc == 0.0:
            sample_vol = 2
        else:
            sample_vol = (3 * 45) / conc
        ws.cell(row=row_index, column=5).value = max(0, 45 - sample_vol)
        ws.cell(row=row_index, column=6).value = sample_vol

wb.save(sys.argv[2] + '.xlsx')

