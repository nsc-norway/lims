import os
import re
import uuid
import tempfile
import datetime
from hubarcode.datamatrix import DataMatrixEncoder
from genologics.lims import *
from genologics import config
from reportlab.lib import colors
from reportlab.graphics.shapes import *
from reportlab.graphics import renderPDF

#template_dir = "C:\\Users\\admin\\Desktop"
#template_dir = "/Users/paalmbj/git/lims/label-printing/templates"
template_dir = "templates"
print_spool_dir = "/tmp"

use_printer = "LABEL1"



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

    d = Drawing(254, 127)
    d.add(Rect(10, 10, 244, 117, fillColor=colors.yellow))
    d.add(String(

    params = {}
    #image_data = DataMatrixEncoder(analyte.id).get_imagedata(cellsize=10)
    image_data = open('test2.png').read()
    params['barcode'] = image_data
    params['project_customer'] = project_customer
    params['project_label'] = project_label
    params['project_date'] = project_date

    params['date'] = datetime.date.today().strftime("%y-%m-%d")
    params['type'] = 'STOCK'
    params['location'] = '0001-A1'

    prepare_odt('tube.odt', 'LABEL1', params)

 

def main():
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    #make_tube_label(Artifact(lims, id = "SUN155A1PA1"))
    make_tube_label(Artifact(lims, id = "FJE56A136PA1"))


main()
