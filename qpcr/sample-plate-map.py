# -*- coding: utf-8 -*-

from genologics.lims import *
from genologics import config
import os
import sys
import datetime
import jinja2

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
print(sys.argv)
process_id, outputfile = sys.argv[1], sys.argv[2]
process = Process(lims, id=process_id)

ios = [(i['uri'], o['uri']) for i, o in process.input_output_maps
        if o['output-generation-type'] == 'PerInput']

artifacts = lims.get_batch(artifact for (i, o) in ios for artifact in [i, o])
lims.get_batch(set(i.samples[0] for i, o in ios))

placements = {o.location[1]: i for i, o in ios}

variables = {
    'server':           config.BASEURI.rstrip("/"),
    'date':             str(datetime.date.today()),
    'container_name':   ios[0][1].location[0].name,
    'user_name':        process.technician.username,
    'placements':       placements
    }
template_loc = os.path.dirname(__file__)
open(outputfile, 'w').write(
        jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_loc)
        ).get_template('plate-map-template.html').render(variables))



