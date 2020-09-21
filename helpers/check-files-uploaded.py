import sys
from genologics.lims import *
from genologics import config

def main(file_ids):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    for file_id in file_ids:
        art = Artifact(lims, id=file_id)
        if not art.files:
            print("The file '{}' is required. Please attach this file and try again.".format(art.name))
            sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1:])

