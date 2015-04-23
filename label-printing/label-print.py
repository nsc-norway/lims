#!/usr/bin/python
# Requirements:
# PIL (use the fork pillow) -- pip install pillow
#  - PIL requires yum packages gcc-c++, zlib-devel (for PNG), python-devel on RHEL6
# huBarcode - pip install hubarcode
# appy - pip install appy
# SciLife Genologics lib - use NSC fork in genologics repo

import os
import re
import sys
import datetime
from appy.pod.renderer import Renderer
from hubarcode.datamatrix import DataMatrixEncoder
from genologics.lims import *
from genologics import config

template_dir = os.path.dirname(os.path.realpath(__file__)) + "/templates"
print_spool_dir = "/remote/label-printing"

class Barcode(object):
    def __init__(self, name, type, cellsize):
        self.name = name
        self.type = type
        self.cellsize = cellsize


use_printer = "LABEL1"

def prepare_odt(template, printer, template_parameters):
    template_path = os.path.join(template_dir, template)
    output_name = "{0}-{1:%Y%m%d%H%M_%f}.odt".format(
            printer,
            datetime.datetime.now()
            )
    output_path = os.path.join(print_spool_dir, "transfer", output_name)
    renderer = Renderer(
            template_path,
            template_parameters,
            output_path,
            pythonWithUnoPath="/Applications/LibreOffice.app/Contents/MacOS/python"
            )
    renderer.run()
    os.rename(output_path, os.path.join(print_spool_dir, output_name))




def make_tube_label(analyte):
    sample = analyte.samples[0]
    project = sample.project
    project_match = re.match(r"(.*)-(.*)-(\d{4}-\d{2}-\d{2})", project.name)
    if project_match:
        project_customer, project_label, project_date = project_match.groups()
    else:
        project_customer = "Invalid"
        project_label = "Project"
        project_date = "Name"

    params = {}
    image_data = DataMatrixEncoder(analyte.id).get_imagedata(cellsize=1)
    params['barcode'] = image_data
    params['project_customer'] = project_customer
    params['project_label'] = project_label
    params['project_date'] = project_date

    params['sample_name'] = sample.name

    params['date'] = datetime.date.today().strftime("%y-%m-%d")
    params['type'] = 'STOCK'
    params['location'] = '0001-A1'

    prepare_odt('tube.odt', 'LABEL1', params)

 

def main(type, lims_ids):

    if type == 'tube':
        do = make_tube_label
    else:
        print "Don't know how to make '", type, "' label"

    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 

    for id in lims_ids:
        do(Artifact(lims, id=id))


main(sys.argv[1], sys.argv[2:])

