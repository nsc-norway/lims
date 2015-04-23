import os
import re
import uuid
import tempfile
import datetime
from appy.pod.renderer import Renderer
from hubarcode.datamatrix import DataMatrixEncoder
from genologics.lims import *
from genologics import config
import PIL

#template_dir = "C:\\Users\\admin\\Desktop"
#template_dir = "/Users/paalmbj/git/lims/label-printing/templates"
template_dir = "templates"
print_spool_dir = "/tmp"

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

 

def main():
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    make_tube_label(Artifact(lims, id = "SUN155A1PA1"))
    #make_tube_label(Artifact(lims, id = "FJE56A136PA1"))


main()
