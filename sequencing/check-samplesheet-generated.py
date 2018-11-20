# Checks that any user-triggered script (button) has completed successfully

import sys
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    file_artifacts = set()
    for i, o in process.input_output_maps:
        if o['output-generation-type'] == 'PerAllInputs':
            file_artifacts.add(o['uri'])
    lims.get_batch(file_artifacts)
    if not any(
            ("Sample Sheet" in f.name or "SampleSheet" in f.name) and f.files
            for f in file_artifacts
            ):
        print("Please generate a sample sheet before you continue.")
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1])

