from genologics.lims import *
from genologics import config

import sys

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

q = Queue(lims, id="1662")
for a in q.artifacts: #pools
    arts = [i['uri'] for i, o in a.parent_process.input_output_maps if o['limsid'] == a.id]
    for ape in arts:
        print "\t".join([ape.samples[0].project.name, ape.samples[0].name, next(iter(ape.reagent_labels))])

