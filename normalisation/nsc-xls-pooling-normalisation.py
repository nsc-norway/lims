import sys
from genologics.lims import *
from genologics import config
import xlwt

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
        pass

    book = xlwt.Workbook()
    sheet1 = book.add_sheet('Sheet1')

    headers = [
            "Pool Name",
            "Dest Cont",
            "Pool Well",
            "Pool Molarity",
            "Pool Volume",
            "Buffer Volume",
            "Sample",
            "Source Cont",
            "Source Well",
            "Sample Molarity",
            "Sample Volume"
            ]

    row = sheet1.row(0)
    for i, header in enumerate(headers):
        row.write(i, header, xlwt.easyxf('pattern: pattern solid, fore_color yellow;'))

    inputs = []
    outputs = []

    step = Step(lims, id=process.id)

    lims.get_batch(process.all_inputs(unique=True) + process.all_outputs(unique=True))
    lims.get_batch(input.samples[0] for input in process.all_inputs(unique=True))

    try:
        norm_conc = process.udf['Pool molarity']
        pool_volume = process.udf['Pool volume']
    except KeyError as e:
        print("Global option for",  str(e), "not specified")
        sys.exit(1)

    error = False # "Soft" error, still will upload the file

    rows = []
    rowid = 1
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
                    print("Molarity of", input.name, "in pool", pool.name, "is",
                          input.udf['Molarity'], ", which is less than the target per-sample molarity",
                          target_sample_conc, ".")
                    error = True

                sample_volumes.append(
                        pool_pool_volume * target_sample_conc / max(input.udf['Molarity'], 0.0000001)
                        )
            except KeyError:
                unknown_molarity.append(input.name)

        if unknown_molarity:
            print("In pool", pool.name, ", the molarity not known for pool constituents", end='')
            print(", ".join(unknown_molarity))
            sys.exit(1)

        buffer_volume = pool_pool_volume - sum(sample_volumes)

        if not error and buffer_volume < 0:
            print("Total sample volume in pool", pool.name, "is", sum(sample_volumes),
                  "uL, which exceeds the target pool volume", pool_pool_volume, ".",
                  "Reduce the pool molarity or the number of samples per pool, and",
                  "try again.")
            error = True

        dest_container = output.location[0].name
        dest_well = output.location[1].replace(":", "")

        first_in_pool = True
        sum_frag_length = 0.0
        for input, sample_volume in sorted(
                zip(pool.inputs, sample_volumes),
                key=get_tuple_key
                ):
            sample_name = input.name
            input_mol_conc = input.udf['Molarity']
            sum_frag_length += input.udf.get('Average Fragment Size', 0.0)
            source_container = input.location[0].name
            source_well = input.location[1].replace(":", "")
            if first_in_pool:
                for j, v in enumerate([
                    pool.name,
                    dest_container,
                    dest_well,
                    round(pool_norm_conc, 2),
                    round(pool_pool_volume, 2),
                    round(buffer_volume, 2),
                    sample_name,
                    source_container,
                    source_well,
                    round(input_mol_conc, 2),
                    round(sample_volume, 2),
                    ]):
                    sheet1.write(rowid, j, v)
                first_in_pool = False
            else:
                for j, v in enumerate([
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    sample_name,
                    source_container,
                    source_well,
                    round(input_mol_conc, 2),
                    round(sample_volume, 2),
                    ]):
                    sheet1.write(rowid, j, v)
            rowid += 1

        pool.output.udf['Average Fragment Size'] = sum_frag_length / len(pool.inputs)


    lims.put_batch(pool.output for pool in step.pools.pooled_inputs)
    book.save(output_file_id)

    sys.exit(1 if error else 0)


main(sys.argv[1], sys.argv[2])

