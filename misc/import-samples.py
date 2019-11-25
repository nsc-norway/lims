from genologics.lims import *
from genologics import config

import sys

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

data = [l.strip() for l in open("samples.txt")]
for line in data:
    proj, sam, index = line.split("\t")
    project = lims.get_projects(name=proj)[0]
    sam = lims.create_sample(sam, project)
    sam.artifact.get()
    sam.artifact.reagent_labels.add(index)
    sam.artifact.put()

