from genologics.lims import *
from genologics import config
import sys
import re

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
p = Process(lims, id=sys.argv[1])
for analyte in p.all_outputs():
    if len(analyte.reagent_labels) == 1:
        index1 = next(iter(analyte.reagent_labels))
        ii = re.match(r"Dummy index (\d+) \(Dummy\d+\)$", index1)
        i = int(ii.group(1))
        analyte.reagent_labels.add("Dummy index {x} (Dummy{x})".format(x=i+48))
        analyte.put()
        print("Updated")

