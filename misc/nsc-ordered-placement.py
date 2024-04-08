from genologics.lims import *
from genologics import config
import sys
import re
from operator import itemgetter as iget

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
process = Process(lims, id=sys.argv[1])
step = Step(lims, id=sys.argv[1])

# Default placement script to place outputs sorted by project and sample name

# Helper function to report non-fatal unexpected issues
def report(message):
    if step.program_status:
        step.program_status.message = message
        step.program_status.status = "WARNING"
        step.program_status.put()
    else:
        print(message)

outputs = [
        o['uri'] for i, o in process.input_output_maps
        if o['output-generation-type'] == 'PerInput'
]
# Cache the samples; needed to retrieve the projects of all outputs
lims.get_batch(outputs)
lims.get_batch(set(s for o in outputs for s in o.samples))

# Get the projects of each output artifact and check that they belong to a single
# project
projects_artifacts = {}
for output in outputs:
    projects = set(sample.project for sample in output.samples)
    if len(projects) > 1:
        report(f"There are multiple projects in the artifact {output.name}. Unable to perform auto-placement.")
        sys.exit(0)
    project = next(iter(projects))
    projects_artifacts.setdefault(project, list()).append(output)

# Setup - is there already a container? I don't know
output_container = next(iter(step.placements.selected_containers))
assert output_container.type.y_dimension['size'] == 8, "Output container must have 8 rows"
assert output_container.type.x_dimension['size'] == 12, "Output container must have 12 columns"

well_ids = [f"{row}:{column}" for column in range(1, 13) for row in "ABCDEFGH"]
well_index = 0

if sum(len(artifacts) for artifacts in projects_artifacts.values()) > 96:
    print("Error: There are too many samples to put in a single 96-well plate.")
    sys.exit(1)

result_placement_list = []
# The projects should be ordered by the project name
for project, artifacts in sorted(projects_artifacts.items(), key=lambda p_s: p_s[0].name):
    print("Project:", project.name)
    # Place artifacts in the output container
    # Within a project, the ordering is based on a numeric prefix in the artifact name.
    prefix_artifacts = []
    irregular_names = False
    for artifact in artifacts:
        m = re.match(r"(\d+)-", artifact.name)
        if m:
            prefix_artifacts.append((int(m.group(1)), artifact))
        else:
            irregular_names = True
            print("Irregular name", artifact.name)
            break
    
    sorted_pfx_art = sorted(prefix_artifacts, key=iget(0))
    # If there are duplicates, we can't do auto-placement for this project. If there are skipped
    # values (not sequential) we just go ahead anyway, because there can be failed samples.
    if any(prev[0] == current[0] for prev, current in zip(prefix_artifacts, prefix_artifacts[1:])):
        irregular_names = True
        print("Project", project.name, "has a duplicate artifact name.")

    # If the names are okay we go ahead and place this project
    if irregular_names:
        report(f"Skipping auto-placement of project {project.name} because it has irregular sample names.")
    else:
        result_placement_list += zip(
                (a.stateless for _, a in sorted_pfx_art),
                ((output_container, well) for well in well_ids[well_index:])
        )
        well_index += len(sorted_pfx_art)

if result_placement_list:
    print("placement list", result_placement_list)
    step.placements.set_placement_list(result_placement_list)
    step.placements.post()

