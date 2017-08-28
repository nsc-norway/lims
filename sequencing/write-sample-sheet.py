# Write sample sheet to a configured location 

# Arguments:
#   * sample_sheet_file_object - LIMS ID
import os
import sys
from genologics.lims import *
from genologics import config

#   * path to store sample sheet
#   * instrument name

def main(sample_sheet_file_object, path, instrument):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    artifact = Artifact(lims, id=sample_sheet_file_object)
    if len(artifact.files) > 0:
        file = artifact.files[0] 
        orig_file_name = os.path.basename(file.original_location)
        filename = "".join(c for c in orig_file_name if c.isalnum() or c in "_-.")
        dest_path = os.path.join(path, instrument.lower(), filename)
        data = file.download()
        with open(dest_path, "w") as f:
            f.write(data)
    else:
        print "Sample sheet file is not ready"
        sys.exit(1)

if __name__ == "__main__":
    main(*sys.argv[1:])

