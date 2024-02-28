from genologics.lims import *
from genologics import config
import sys
import operator

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
process = Process(lims, id=sys.argv[1])
step = Step(lims, id=sys.argv[1])

# This script should run at the start of the step. It will perform checks about the step setup, and
# then put the outputs artifacts in the selected output container (tube strip)

# Setup
output_container = next(iter(step.placements.selected_containers))
output_num_lanes = output_container.type.y_dimension['size']
rows = "ABCDEFGH"

def report(message):
    step.program_status.message = message
    step.program_status.status = "WARNING"
    step.program_status.put()

# Iterate through the samples and record the input containers, positions and output artifacts
input_location_output = []
# The list will contain:
#    [(input_container, column, row_index, output_artifact), ...]
# row_index is the numerical index of the row, starting at 0
for i, o in process.input_output_maps:
    if o['output-generation-type'] == 'PerInput' and o['output-type'] == 'Analyte':
        output = o['uri']
        input = i['uri']
        row, col = input.location[1].split(":")
        input_location_output.append((input.location[0], int(col), rows.index(row), output.stateless))

# Check sample count
if len(input_location_output) < output_num_lanes:
    report("There are not enough inputs for the number of lanes. Make sure you choose the right container type in the previous page. Manual placement is enabled.")
    sys.exit(0)
elif len(input_location_output) > output_num_lanes:
    print(f"There are too many inputs to put in the container type {output_container.type.name}. Aborting.")
    sys.exit(1)

# Check input container
num_containers = len(set(cont.id for cont, _, _, _ in input_location_output))
if num_containers != 1:
    report(f"Found inputs from {num_containers} containers, but only one input container is allowed. Perform manual placement.")
    sys.exit(0)

# Check columns
input_columns = set([column for _, column, _, _ in input_location_output])
if len(input_columns) > 1:
    report(f"Found inputs from columns {input_columns}, but only one column should be processed at a time. Perform manual placement.")
    sys.exit(0)

# Sort by row (alphabetically) which is item 2
sorted_list = sorted(input_location_output, key=operator.itemgetter(2))
# Place the outputs automatically. There should be exactly the correct number of inputs and outputs now.
# Check if the inputs are in the correct source rows. If the target is a 2-strip tube and the source rows are
# not A and B we silently fallback to manual placement.
if all(r1 == r2 for r1, r2 in zip(range(output_num_lanes), [item[2] for item in sorted_list])):
    placements = [
        (output, (output_container, f"{row_index+1}:1"))
        for _, col, row_index, output in sorted_list
    ]
    step.placements.set_placement_list(placements)
    step.placements.post()


