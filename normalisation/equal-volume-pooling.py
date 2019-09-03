import sys
import csv
from genologics.lims import *
from genologics import config

def get_row_key(row):
    container = row[2]
    well = row[3]
    row, col = well.split(":")
    return (container, int(col), row)
    

def get_or_set(entity, udf, default_value):
    try:
        return entity.udf[udf]
    except KeyError:
        entity.udf[udf] = default_value
        return default_value

def main(process_id, pool_volume_param, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    # Clear the file, to make sure old data don't remain
    with open(output_file_id, 'w') as f:
        f.write("")

    header = [
            "Pool",
            "Dest_container",
            "Well",
            "Pool_volume",
            "Sample",
            "Source_container",
            "Well",
            "Volume_uL",
            ]


    step = Step(lims, id=process.id)

    inputs = process.all_inputs(unique=True)
    lims.get_batch(inputs + process.all_outputs(unique=True))
    lims.get_batch(input.samples[0] for input in inputs)

    rows = []
    for pool in step.pools.pooled_inputs:
        output = pool.output # output already fetched in batch, as process input

        dest_container = output.location[0].name
        dest_well = output.location[1]

        total_pool_volume_ul = int(pool_volume_param)
        sample_volume = total_pool_volume_ul / len(pool.inputs)
        sample_vol_str = "%4.2f" % sample_volume
        
        first_in_pool = True
        for input in pool.inputs:
            sample_name = input.name
            source_container = input.location[0].name
            source_well = input.location[1]
            if first_in_pool:
                rows.append([
                    pool.name,
                    dest_container,
                    dest_well,
                    "%4.2f" % total_pool_volume_ul,
                    sample_name,
                    source_container,
                    source_well,
                    sample_vol_str,
                    ])
                first_in_pool = False
            else:
                rows.append([
                    "",
                    "",
                    "",
                    "",
                    sample_name,
                    source_container,
                    source_well,
                    sample_vol_str,
                    ])


    lims.put_batch(pool.output for pool in step.pools.pooled_inputs)

    with open(output_file_id, 'w', encoding="utf-8") as out_file:
        for row in [header] + rows:
            out_file.write(",".join(row) + "\n")

main(*sys.argv[1:])

