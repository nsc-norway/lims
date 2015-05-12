from genologics.lims import *
from genologics import config
from collections import defaultdict
import sys

def main(category, analyte_ids):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

    for analyte_id in analyte_ids:
        ana = Artifact(lims, id = analyte_id)
        ana.reagent_labels.clear()
        ana.put()


main(sys.argv[1:])
