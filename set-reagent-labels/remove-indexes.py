from genologics.lims import *
from genologics import config
import sys

def main(analyte_ids):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

    for analyte_id in analyte_ids:
        ana = Artifact(lims, id = analyte_id)
        ana.reagent_labels.clear()
        ana.put()


main(sys.argv[1:])
