import sys
import xlwt

from genologics.lims import *
from genologics import config

#from openpyxl.styles import Border, Side, Alignment, Font
from openpyxl import Workbook

TUBE = 'Tube'

def get_well_key(artifact):
    container = artifact.location[0].name
    well = artifact.location[1]
    row, col = well.split(":")
    return (container, int(col), row)
    
def display_well(wel):
    return wel[0] + wel[2:]

def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    inputs = []
    outputs = []
    step = Step(lims, id=process.id)
    lims.get_batch(process.all_inputs(unique=True) + process.all_outputs(unique=True))
    lims.get_batch(input.samples[0] for input in process.all_inputs(unique=True))

    input_tubes = sorted(set(
                        int(inp.location[0].id.partition("-")[2]) for inp in process.all_inputs()
                                if inp.location[0].type_name == TUBE
                    ))
    output_tubes = sorted(set(
                        int(oup.location[0].id.partition("-")[2]) for oup in process.all_outputs()
                                if oup.type == 'Analyte' and oup.location[0].type_name == TUBE
                    ))

    book = xlwt.Workbook()
    sheet1 = book.add_sheet('Sheet1')

    headers = [
            "Source Well",
            "Destination Well",
            "Sample Volume",
            "Pool Volume"
            ]
    row_index = 0
    row = sheet1.row(row_index)
    for i, header in enumerate(headers):
        row.write(i, header)
    try:
        norm_conc = process.udf['Pool molarity']
        pool_volume = process.udf['Pool volume']
    except KeyError as e:
        print("Error: option for default",  str(e), "not specified.")
        sys.exit(1)

    for pool in step.pools.pooled_inputs:
        output = pool.output
        pool_norm_conc = output.udf.get('Normalized conc. (nM)', norm_conc)
        pool_pool_volume = output.udf.get('Volume (uL)', pool_volume)

        target_sample_conc = pool_norm_conc * 1.0 / len(pool.inputs)

        if output.location[0].type_name == TUBE:
            dest_well = output_tubes.index(int(output.location[0].id.partition("-")[2])) + 1
        else:
            dest_well = display_well(output.location[1])
        first_in_pool = True
        for input in sorted(pool.inputs, key=get_well_key):
            try:
                sample_volume = pool_pool_volume * target_sample_conc / max(input.udf['Molarity'], 0.0000001)
            except KeyError:
                print("In pool", pool.name, ", the molarity is not known for pool constituent: ",
                        input.name)
                return 1
            row_index += 1
            row = sheet1.row(row_index)
            if input.location[0].type_name == TUBE:
                source_well = input_tubes.index(int(input.location[0].id.partition("-")[2])) + 1
            else:
                source_well = display_well(input.location[1])
            row.write(0, source_well)
            row.write(1, dest_well)
            row.write(2, round(sample_volume, 1))
            if first_in_pool:
                row.write(3, round(pool_pool_volume, 1))
                first_in_pool = False

    book.save(output_file_id)
    return 0

sys.exit(main(sys.argv[1], sys.argv[2]))

