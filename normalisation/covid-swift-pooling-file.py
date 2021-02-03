import sys
from genologics.lims import *
from genologics import config


def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    # Clear the file, to make sure old data don't remain
    with open(output_file_id + ".csv", 'w') as f:
        f.write(",".join([
                "Input pool",
                "Molarity of input pool (nM)",
                "Volume to add (uL)"
                ]) + "\n")
        step = Step(lims, id=process.id)

        if len(step.pools.pooled_inputs) > 1:
            print("This simple script is unable to produce multiple pools. Go through the step multiple times instead.")
            sys.exit(1)
        pooled = step.pools.pooled_inputs[0]

        # Pre-cache inputs
        inputs = process.all_inputs(resolve=True)

        # Parameter for volume
        try:
            pool_volume = process.udf['Total pool volume (uL)']
            pool_molarity = process.udf['Pool molarity (nM)']
        except KeyError as e:
            print("Error: '" + str(e) + "' not specified.")
            sys.exit(1)

        num_inputs = len(pooled.inputs)
        input_volumes_sum = 0
        # Write a line to the file for each pool input
        for input in pooled.inputs:
            try:
                input_molarity = input.udf['Molarity']
            except KeyError:
                print("Error: The Molarity field of", input.name, "is not set.")
                sys.exit(1)
            input_conc_in_pool = pool_molarity / num_inputs
            input_pool_volume = (input_conc_in_pool * pool_volume) / input_molarity
            input_volumes_sum += input_pool_volume
            f.write("{},{},{:.1f}\n".format(input.name, input_molarity, input_pool_volume))
    pooled.output.udf['Molarity'] = process.udf['Pool molarity (nM)']
    pooled.output.udf['Normalized conc. (nM)'] = process.udf['Pool molarity (nM)']
    pooled.output.put()

    if input_volumes_sum > pool_volume * 1.001: # could have small floating point error..
        print("Warning: Target pool molarity is too high.".format(
            pool_volume
        ))
        sys.exit(1)
    if input_volumes_sum < pool_volume * 0.999:
        print("Warning: Target pool molarity is too low.".format(
            pool_volume
        ))
        sys.exit(1)

main(sys.argv[1], sys.argv[2])

