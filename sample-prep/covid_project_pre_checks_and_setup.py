import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id):
    """Function to do some sanity checks on project entry. Verify that index
    plate matches the selected reagent plate."""
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    step = Step(lims, id=process_id)

    ## --- 1: Check that correct plate was selected ---
    inputs = process.all_inputs(resolve=True)
    samples = lims.get_batch([s for input in inputs for s in input.samples])
    projects = set([s.project for s in samples])
    project_index_plates = set()
    for p in projects:
        m = re.match(r"\d+-([NS]\d)-.*", p.name)
        if m:
            project_index_plates.add(m.group(1))

    if len(project_index_plates) == 1:
        plate_string = next(iter(project_index_plates))
        correct_answer = {
            "S1": "SwiftUDI Plate 1",
            "S2": "SwiftUDI Plate 2",
            "S3": "SwiftUDI Plate 3",
            "S4": "SwiftUDI Plate 4",
            "N1": "NimaGen U01v2",
            "N2": "NimaGen U02",
            "N3": "NimaGen U03",
            "N5": "NimaGen U05",
            "N6": "NimaGen U06"
        }
        if plate_string not in correct_answer:
            print("Project name string {} is not a known plate type.".format(plate_string))
            sys.exit(1)
        if step.reagents.reagent_category != correct_answer[plate_string]:
            print("Selected index plate '{}' does not match project name '{}'.".format(
                step.reagents.reagent_category, plate_string))
            sys.exit(1)
    elif len(project_index_plates) > 1:
        print("Error: Mutliple projects selected, with different index plate numbers. Only add one project to this step.")
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1])
