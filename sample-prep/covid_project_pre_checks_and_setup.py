import sys
import re
from genologics.lims import *
from genologics import config
import requests

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
    project_short_names = []

    for project in projects:
        m = re.match(r"\d+-([NS]\d)-([^-]+).*", project.name)
        m_new_fhi_name = re.match(r"(FHI\d+)-(S\d)-([^-]+).*", project.name)
        if m:
            plate_string = m.group(1)
            project_short_names.append(m.group(2))
        elif m_new_fhi_name:
            plate_string = m_new_fhi_name.group(2)
            project_short_names.append(m_new_fhi_name.group(1))
        else:
            print("Project name should contain index plate number Sn and NSC project ID (FHIxxx). "
                 "Valid formats: 20221214-S4-MIK411-221212 OR FHI333-S2-EXT-20230104-07. "
                 "Failed to parse project: "  + project.name + ".")
            sys.exit(1)
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

    # Auto-placement in same pattern as inputs (but possibly from multiple plates)
    output_container = next(iter(step.placements.selected_containers))
    output_container.name = "_".join(project_short_names) + " Prep"
    output_container.put()

    placements = []
    for i, o in process.input_output_maps:
        well = i['uri'].location[1]
        placements.append((o['uri'].stateless, (output_container, well)))
    step.placements.set_placement_list(placements)
    try:
        step.placements.post()
    except requests.exceptions.HTTPError as e:
        print("Sample placements are invalid. Verify that you selected the right projects. Error:", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1])
