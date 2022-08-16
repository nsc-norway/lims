import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

TUBE = 'Tube'

def get_tuple_key(tupl):
    artifact = tupl[0]
    container = artifact.location[0].name
    well = artifact.location[1]
    row, col = well.split(":")
    return (container, int(col), row)
    

def get_or_set(entity, udf, default_value):
    try:
        return entity.udf[udf]
    except KeyError:
        entity.udf[udf] = default_value
        return default_value

def main(process_id, output_file_id):
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
            "Pool molarity",
            "Pool volume",
            "Buffer volume",
            "Sample",
            "Source cont.",
            "Well",
            "Sample molarity",
            "Sample volume"
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
        print "Global option for",  str(e), "not specified"
        print "This is used in case the per-pool value is not given for some pools"
        sys.exit(1)

    input_tubes = sorted(set(
        int(inp.location[0].id.partition("-")[2]) for inp in process.all_inputs()
        if inp.location[0].type_name == TUBE
    ))
    output_tubes = sorted(set(
        int(oup.location[0].id.partition("-")[2]) for oup in process.all_outputs()
        if oup.type == 'Analyte' and oup.location[0].type_name == TUBE
    ))

    error = False # "Soft" error, still will upload the file

    rows = []
    for pool in step.pools.pooled_inputs:
        output = pool.output # output already fetched in batch, as process input
        pool_norm_conc = get_or_set(output, 'Normalized conc. (nM)', norm_conc)
        pool_pool_volume = get_or_set(output, 'Volume (uL)', pool_volume)

        target_sample_conc = pool_norm_conc * 1.0 / len(pool.inputs)
        target_sample_conc_str = "%4.2f" % target_sample_conc
        sample_volumes = []
        unknown_molarity = []
        for input in pool.inputs:
            try:
                if not error and input.udf['Molarity'] < target_sample_conc:
                    print "Molarity of", input.name, "in pool", pool.name, "is",
                    print input.udf['Molarity'], ", which is less than the target per-sample molarity",
                    print target_sample_conc, "."
                    error = True

                sample_volumes.append(
                        pool_pool_volume * target_sample_conc / max(input.udf['Molarity'], 0.0000001)
                        )
            except KeyError:
                unknown_molarity.append(input.name)

        if unknown_molarity:
            print "In pool", pool.name, ", the molarity not known for pool constituents",
            print ", ".join(unknown_molarity)
            sys.exit(1)

        buffer_volume = pool_pool_volume - sum(sample_volumes)

        if not error and buffer_volume < 0:
            print "Total sample volume in pool", pool.name, "is", sum(sample_volumes),
            print "uL, which exceeds the target pool volume", pool_pool_volume, ".",
            print "Reduce the pool molarity or the number of samples per pool, and",
            print "try again."
            error = True

        dest_container = output.location[0].name.encode('utf-8')
        if output.location[0].type_name == TUBE:
            dest_well = output_tubes.index(int(output.location[0].id.partition("-")[2])) + 1
        else:
            dest_well = output.location[1]

        first_in_pool = True
        for input, sample_volume in sorted(
                zip(pool.inputs, sample_volumes),
                key=get_tuple_key
                ):
            sample_name = input.name.encode('utf-8')
            input_mol_conc = input.udf['Molarity']
            input_mol_conc_str = "%4.2f" % (input.udf['Molarity'])
            sample_vol_str = "%4.2f" % sample_volume
            source_container = input.location[0].name.encode('utf-8')
            if input.location[0].type_name == TUBE:
                source_well = input_tubes.index(int(input.location[0].id.partition("-")[2])) + 1
            else:
                source_well = input.location[1]
            if first_in_pool:
                rows.append([
                    pool.name.encode('utf-8'),
                    dest_container,
                    dest_well,
                    "%4.2f" % pool_norm_conc,
                    "%4.2f" % pool_pool_volume,
                    "%4.2f" % buffer_volume,
                    sample_name,
                    source_container,
                    source_well,
                    input_mol_conc_str,
                    sample_vol_str,
                    ])
                first_in_pool = False
            else:
                rows.append([
                    "",
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
                    ])


    lims.put_batch(pool.output for pool in step.pools.pooled_inputs)

    with open(output_file_id, 'wb') as out_file:
        out = csv.writer(out_file)
        out.writerow(header)
        out.writerows(rows)

    sys.exit(1 if error else 0)


main(sys.argv[1], sys.argv[2])

