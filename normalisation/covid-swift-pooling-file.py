import sys
from genologics.lims import *
from genologics import config


def main(process_id, output_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    # Clear the file, to make sure old data don't remain
    with open(output_file_id + ".csv", 'wb') as f:
        f.write(",".join([
                "Input pool",
                "Concentration (ng/uL)",
                "Volume (uL)"
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
        except KeyError as e:
            print("Error: '" + str(e) + "' not specified.")
            sys.exit(1)

        # Write a line to the file for each pool input
        for input in pooled.inputs:
            try:
                input_molarity = input.udf['Molarity']
            except KeyError:
                print("Error: The Molarity field of", input.name, "is not set.")
                sys.exit(1)

            pool_input_vol = str("TODO_SORRY")
            print("{},{},{}\n".format(input.name, input_molarity, pool_input_vol))

        process.udf['Pool molarity (nM)'] = 4.0
        process.put()
        pooled.output.udf['Molarity'] = process.udf['Pool molarity']
        pooled.output.put()

main(sys.argv[1], sys.argv[2])

