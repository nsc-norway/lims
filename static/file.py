import sys
import os
from genologics.lims import *
from genologics import config

def main(file_id, filename):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    f = Artifact(lims, id=file_id)
    gs = lims.glsstorage(f, filename)
    file_obj = gs.post()
    filepath = os.path.join(os.path.dirname(__file__), filename)
    file_obj.upload(open(filepath).read())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

