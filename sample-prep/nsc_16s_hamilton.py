import sys
import re
import xlwt
from genologics.lims import *
from genologics import config

# Script to excel file for Hamilton robot

def well_sort_key(analyte):
    row, _, scol = analyte.location[1].partition(":")
    return (analyte.location[0].id, int(scol), row)

def main(process_id, file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    book = xlwt.Workbook()
    sheet1 = book.add_sheet('Sheet1')

    sheet1.write(0, 0, 'Sample Name')
    sheet1.write(0, 1, 'Plate Number')
    sheet1.write(0, 2, 'Sample Position')
    sheet1.write(0, 3, 'Stock Conc')
    sheet1.write(0, 4, 'Sample Input')
    sheet1.write(0, 5, 'Buffer Volume')
    sheet1.write(0, 6, 'Forward Primer')
    sheet1.write(0, 7, 'Reverse Primer')

    outputs = lims.get_batch(o['uri'] for i,o in process.input_output_maps
                    if o['output-type'] == "Analyte")
    
    #TODO: complete this file
    for i, output in enumerate(sorted(outputs, key=well_sort_key), 1):
        output_well = output.location[1][:1]+output.location[1][2:]
        reagent = next(iter(output.reagent_labels))
        scol, row = re.match(r"SureSelect XT2 Index (\d{2})-([A-H]).*", reagent).groups((1,2))
        adapter_well = "%s%d" % (row, int(scol))
        sheet1.write(i, 0, output_well)
        sheet1.write(i, 1, adapter_well)

    book.save(file_id + "-InputSheet.xls")


# Use:  main PROCESS_ID FILE_ID
main(sys.argv[1], sys.argv[2])

