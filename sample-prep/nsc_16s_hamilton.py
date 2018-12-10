import sys
import re
import xlwt
from genologics.lims import *
from genologics import config

# Script to excel file for Hamilton robot
MAX_BUFFER_ALERT = 300

def get_container_well(analyte):
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

    i_os = [(i['uri'], o['uri']) for i,o in process.input_output_maps
                    if o['output-type'] == "Analyte"]
    lims.get_batch([a[0] for a in i_os] + [a[1] for a in i_os])
    
    buffer_alert_samples = []
    plates = set()
    # Get container ID and well for outputs
    coordinates = map(get_container_well, (a[1] for a in i_os))
    # List of: [ ((container_ID, col, row), (input, output), ...]
    data = sorted(list(zip(coordinates, i_os)))
    for i, ((container, col, row), (input, output)) in enumerate(data, 1):
        sheet1.write(i, 0, output.name)
        plates.add(container)
        sheet1.write(i, 1, len(plates))
        sheet1.write(i, 2, "{}{}".format(row, col))
        if output.control_type:
            sheet1.write(i, 3, int(output.control_type.concentration))
            sheet1.write(i, 4, 0)
            sheet1.write(i, 5, 0)
            output.udf['Input (uL)'] = 0
        else:
            input_conc = input.udf['Concentration']
            if input_conc == 0.0: input_conc = 0.00001
            try:
                input_vol = output.udf['Input (uL)']
            except KeyError:
                input_vol = process.udf['Input (uL)']
                output.udf['Input (uL)'] = input_vol
            sheet1.write(i, 3, input_conc)
            sheet1.write(i, 4, input_vol)
            target_conc = process.udf['Target conc. (ng/uL)']
            buffer_vol = input_vol * (input_conc / target_conc - 1.0)
            sheet1.write(i, 5, max(0, buffer_vol))
            if buffer_vol > MAX_BUFFER_ALERT:
                buffer_alert_samples.append(output.name)

        # Indexing
        reagent = next(iter(output.reagent_labels))
        reverse, forward = re.match(r"16S_... \(R(\d{2})-F(\d{2})\)", reagent).groups((1,2))
        sheet1.write(i, 6, int(forward))
        sheet1.write(i, 7, int(reverse))

    lims.put_batch(a[1] for a in i_os)
    book.save(file_id + "-InputSheet.xls")
    if buffer_alert_samples:
        print ("Warning: buffer volume exceeds", MAX_BUFFER_VOL, "for samples: ",\
                ", ".join(buffer_alert_samples), ".")
        sys.exit(1)


# Use:  main PROCESS_ID FILE_ID
main(sys.argv[1], sys.argv[2])

