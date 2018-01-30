import sys
from genologics.lims import *
from genologics import config

def main(process_id, output_file):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    container_output = {}
    for i, o in process.input_output_maps:
        if o['output-generation-type'] == "PerInput":
            container_output[o['uri'].location] = o['uri']

    containers = set(loc[0] for loc in container_output)

    if len(containers) > 1:
        print("Error: currently only one plate is supported, {0} were provided".format(len(containers)))
        sys.exit(1)

    container = next(iter(containers))

    # Clear the file, to make sure old data don't remain
    with open(output_file, 'wb') as f:
        assert container.type.name == '96 well plate'
        for row in 'ABCDEFGH':
            row_has_output = False
            for col in range(1, 13):
                output = container_output.get((container, "{0}:{1}".format(row, col)))
                if output:
                    row_has_output = True
                    f.write(output.name + "\r\n")
                elif col == 12 and row_has_output:
                    f.write("LADDER\r\n")
                else:
                    f.write("\r\n")


main(sys.argv[1], sys.argv[2])

