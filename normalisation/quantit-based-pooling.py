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
    

def get_or_set(entity, udf, default_value):
    try:
        return entity.udf[udf]
    except KeyError:
        entity.udf[udf] = default_value
        return default_value

def main(process_id, def_sample_dna_quantity, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    # Clear the file, to make sure old data don't remain
    with open(output_file_id, 'wb') as f:
        f.write("")

    out_buf = StringIO.StringIO()   

    header = [
            "Pool",
            "Dest. cont.",
            "Well",
            "Sample",
            "Source cont.",
            "Well",
            "Sample conc. (ng/uL)",
            "Pooling volume (uL)",
            "Sample norm. amount DNA",
            ]


    step = Step(lims, id=process.id)

    inputs = process.all_inputs(unique=True)
    lims.get_batch(inputs + process.all_outputs(unique=True))
    lims.get_batch(input.samples[0] for input in inputs)

    try:
        qc_results = lims.get_qc_results(inputs, "Quant-iT QC Diag 1.1")
    except KeyError, e:
        print "Missing QC result for", e
        sys.exit(1)
    lims.get_batch(qc_results)
    qc_result_map = dict((input, qc_result) for input, qc_result in zip(inputs, qc_results))

    error = False # "Soft" error, still will upload the file

    rows = []
    for pool in step.pools.pooled_inputs:
        output = pool.output # output already fetched in batch, as process input
        target_sample_qty = get_or_set(output, 'Amount of DNA per sample (ng)', float(def_sample_dna_quantity))
        target_sample_qty_str = "%4.2f" % target_sample_qty

        sample_concs = []
        unknown_qc = []
        for input in pool.inputs:
            try:
                concentration = qc_result_map[input].udf['Concentration']
                sample_concs.append(concentration)
            except KeyError:
                unknown_qc.append(input.name)

        if unknown_qc:
            print "In pool", pool.name, ", the concentration is not known for pool constituents",
            print ", ".join(unknown_qc), "."
            sys.exit(1)

        dest_container = output.location[0].name
        dest_well = output.location[1]

        first_in_pool = True
        for input, sample_conc in zip(pool.inputs, sample_concs):
            sample_name = input.name.encode('utf-8')
            input_conc_str = "%4.2f" % (sample_conc)
            pooling_volume = target_sample_qty / sample_conc
            pooling_vol_str = "%4.2f" % pooling_volume
            source_container = input.location[0].name
            source_well = input.location[1]
            if first_in_pool:
                rows.append([
                    pool.name,
                    dest_container,
                    dest_well,
                    sample_name,
                    source_container,
                    source_well,
                    input_conc_str,
                    pooling_vol_str,
                    target_sample_qty_str,
                    ])
                first_in_pool = False
            else:
                rows.append([
                    "",
                    "",
                    "",
                    sample_name,
                    source_container,
                    source_well,
                    input_conc_str,
                    pooling_vol_str,
                    target_sample_qty_str,
                    ])


    lims.put_batch(pool.output for pool in step.pools.pooled_inputs)

    with open(output_file_id, 'wb') as out_file:
        out = csv.writer(out_file)
        out.writerow(header)
        out.writerows(rows)

    sys.exit(1 if error else 0)


main(*sys.argv[1:])

