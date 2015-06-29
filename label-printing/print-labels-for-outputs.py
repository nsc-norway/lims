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
import tempfile
from appy.pod.renderer import Renderer
from hubarcode.datamatrix import DataMatrixEncoder
from genologics.lims import *
from genologics import config
from ooopy.OOoPy import OOoPy
from ooopy.Transformer  import Transformer
import ooopy.Transforms as     Transforms

template_dir = os.path.dirname(os.path.realpath(__file__)) + "/templates"
print_spool_dir = "/remote/label-printing"

def prepare_odt(template, template_parameters, output_path):
    template_path = os.path.join(template_dir, template)
    renderer = Renderer(
            template_path,
            template_parameters,
            output_path
            )
    renderer.run()


def make_tube_label(analyte, sample_type, outputfile):
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
    # Norwegian keyboard map for barcode scanner, need to change symbols
    barcode_string = analyte.id.replace("-", "/")
    image_data = DataMatrixEncoder(analyte.id).get_imagedata(cellsize=1)
    params['barcode'] = image_data
    params['project_customer'] = project_customer
    params['project_label'] = project_label
    params['project_date'] = project_date

    params['sample_name'] = analyte.name

    params['date'] = datetime.date.today().strftime("%y-%m-%d")
    params['type'] = sample_type
    container = analyte.location[0]
    well = analyte.location[1].replace(":","")
    params['container'] = container.name
    if container.type.name == "Tube":
        params['well'] = ""
    else:
        params['well'] = well

    prepare_odt('tube.odt', params, outputfile)

 

def main(sample_type, process_id):

    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)

    result_name = "LABEL1-{0:%Y%m%d%H%M_%f}.odt".format(datetime.datetime.now())
    transfer_output_path = os.path.join(print_spool_dir, "transfer", result_name)
        
    files = []
    analytes = process.analytes()[0] # analytes() returns tuples (Analyte, 'Output')
    key_func = lambda a: (a.location[0].name,) + tuple(reversed(a.location[1].split(":")))
    for ana in sorted(analytes, key=key_func):
        outputfile = tempfile.NamedTemporaryFile(suffix='.odt')
        outputfile.close()
        make_tube_label(ana, sample_type, outputfile.name)
        files.append(outputfile.name)

    ooopy = OOoPy(infile = files[0], outfile=transfer_output_path)
    if len(analytes) > 1:
        t = Transformer \
            ( ooopy.mimetype
            , Transforms.get_meta        (ooopy.mimetype)
            , Transforms.Concatenate     (* (files [1:]))
            , Transforms.renumber_all    (ooopy.mimetype)
            , Transforms.set_meta        (ooopy.mimetype)
            , Transforms.Fix_OOo_Tag     ()
            , Transforms.Manifest_Append ()
            )
        t.transform (ooopy)
    ooopy.close()

    os.rename(transfer_output_path, os.path.join(print_spool_dir, result_name))

main(sys.argv[1], sys.argv[2])


