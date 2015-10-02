import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

def get_row_key(row):
    container = row[2]
    well = row[3]
    row, col = well.split(":")
    return (container, int(col), row)
    

def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    out_buf = StringIO.StringIO()   

    header = [
            "Pool",
            "Dest. cont.",
            "Well",
            "Pool volume",
            "Buffer volume",
            "Sample",
            "Source cont.",
            "Well",
            "Sample molarity",
            "Sample volume",
            "Sample normalised conc.",
            ]


    inputs = []
    outputs = []

    step = Step(lims, id=process.id)

    lims.get_batch(process.all_inputs(unique=True) + process.all_outputs(unique=True))
    lims.get_batch(input.samples[0] for input in process.all_inputs(unique=True))

    try:
        norm_conc = process.udf['Pool molarity']
        pool_volume = process.udf['Pool volume']
    except KeyError, e:
        print str(e), "not specified"
        sys.exit(1)

    rows = []
    for pool in step.pools.pooled_inputs:
        output = pool.output # output already fetched in batch, as process input
        output.udf['Normalized conc. (nM)'] = norm_conc

        target_sample_conc = norm_conc * 1.0 / len(pool.inputs)
        target_sample_conc_str = "%4.2f" % target_sample_conc
        sample_volumes = [pool_volume * target_sample_conc / input.udf['Molarity'] for input in pool.inputs]
        buffer_volume = pool_volume - sum(sample_volumes)

        if buffer_volume < 0:
            print "Total sample volume in pool exceeds", pool_volume, "uL. Reduce the Pool volume and try "\
                   "again."
            sys.exit(1)

        dest_container = output.location[0].name
        dest_well = output.location[1]

        first_in_pool = True
        for input, sample_volume in zip(pool.inputs, sample_volumes):
            sample_name = input.name.encode('utf-8')
            input_mol_conc = input.udf['Molarity']
            input_mol_conc_str = "%4.2f" % (input.udf['Molarity'])
            sample_vol_str = "%4.2f" % sample_volume
            source_container = input.location[0].name
            source_well = input.location[1]
            if first_in_pool:
                rows.append([
                    pool.name,
                    dest_container,
                    dest_well,
                    "%4.2f" % pool_volume,
                    "%4.2f" % buffer_volume,
                    sample_name,
                    source_container,
                    source_well,
                    input_mol_conc_str,
                    sample_vol_str,
                    target_sample_conc_str,
                    ])
                first_in_pool = False
            else:
                rows.append([
                    "",
                    "",
                    "",
                    "",
                    "",
                    sample_name,
                    source_container,
                    source_well,
                    input_mol_conc_str,
                    sample_vol_str,
                    target_sample_conc_str,
                    ])


    lims.put_batch(pool.output for pool in step.pools.pooled_inputs)

    with open(output_file_id, 'wb') as out_file:
        out = csv.writer(out_file)
        out.writerow(header)
        out.writerows(rows)


main(sys.argv[1], sys.argv[2])

