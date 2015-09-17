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
        project_customer = project.name
        project_label = ""
        project_date = ""

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

 
def sort_key_func(analyte):
    row, col = analyte.location[1].split(":")
    return (analyte.location[0].name, int(col), row)


def filter_print_range(ranges, sorted_analytes):
    """Yield only analytes in the specified range. Ranges specified with 
    hyphen or with single pages.
    N-M, N2-M2, N3
    Doesn't handle all corner cases, if our users are difficult on purpose.
    (would use a generator, but need to throw exception when called, so 
    returning a list instead)
    """
    range_specs = ranges.split(",")
    accept_ranges = []
    for range_spec in range_specs:
        start_end = range_spec.split("-")
        start = int(start_end[0]) - 1
        if len(start_end) == 1:
            end = int(start_end[0]) - 1
        elif len(start_end) == 2:
            end = int(start_end[1]) - 1
        else:
            raise ValueError("Invalid range specification")
        accept_ranges.append((start, end))
    accept_ranges.sort()
    irange = 0
    filtered = []
    for i, ana in enumerate(sorted_analytes):
        while irange < (len(accept_ranges)-1) and i > accept_ranges[irange][1]:
            irange += 1
        if i >= accept_ranges[irange][0] and i <= accept_ranges[irange][1]:
            filtered.append(ana)
    return filtered


def main(sample_type, lims_ids):

    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 

    result_name = "LABEL1-{0:%Y%m%d%H%M_%f}.odt".format(datetime.datetime.now())
    transfer_output_path = os.path.join(print_spool_dir, "transfer", result_name)
        
    files = []
    if len(lims_ids) == 1:
        process = Process(lims, id=lims_ids[0])
        outputs = process.all_outputs(unique=True)
    elif len(lims_ids) > 1 and lims_ids[0] == "ANALYTES":
        process = None
        outputs = [Artifact(lims, id=lims_id) for lims_id in lims_ids[1:]]
    else:
        print "Invalid argument, use either process-ID or ANALYTES and a list of analytes"
        sys.exit(1)
        
    outputs = lims.get_batch(outputs)
    analytes = filter(lambda a: a.type == 'Analyte', outputs)
    lims.get_batch(list(set(analyte.samples[0] for analyte in analytes)))
    to_print = sorted(analytes, key=sort_key_func)

    if process:
        try:
            to_print = filter_print_range(process.udf['Label print range'], to_print)
        except KeyError:
            pass
        except ValueError:
            print "Invalid format for the print range. Use format N1-M1, N2-M2, N3."
            sys.exit(1)

    for ana in to_print:
        outputfile = tempfile.NamedTemporaryFile(suffix='.odt')
        outputfile.close()
        if sample_type == "auto":
            if len(ana.samples) > 1:
                sample_type = "pool"
            else:
                try:
                    conc = ana.udf['Normalized conc. (nM)']
                    sample_type = "norm_conc"
                except KeyError:
                    sample_type = "molarity"

        if sample_type == "norm_conc": # can be norm_conc, molarity, pool or a fixed name preceded by :
            try:
                sample_type_label = "%4.1fnM" % ana.udf['Normalized conc. (nM)']
            except KeyError:
                print "Normalised concentration not known for", ana.name, "(use Compute first)"
                sys.exit(1)
        elif sample_type == "pool": # can be norm_conc, molarity, pool or a fixed name preceded by :
            try:
                sample_type_label = "%4.1fnM P" % ana.udf['Normalized conc. (nM)']
            except KeyError:
                print "Normalised concentration not known for", ana.name, "(please enter in table)"
                sys.exit(1)
        elif sample_type == "molarity":
            try:
                sample_type_label = "%4.1fnM" % ana.udf['Molarity']
            except KeyError:
                print "Requestsed to print molarity, but not available"
                sys.exit(1)
        elif sample_type.startswith("TEXT:"):
            sample_type_label = sample_type[5:]
        else:
            print "Invalid sample type '", sample_type, "' in command line"
            sys.exit(1)

        make_tube_label(ana, sample_type_label, outputfile.name)
        files.append(outputfile.name)

    if not files:
        print "No labels to print"
        sys.exit(0)

    ooopy = OOoPy(infile = files[0], outfile=transfer_output_path)
    if len(files) > 1:
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

# Use args: sample_type process_id
# or:       sample_type "ANALYTES" sample_id1 [sample_id2 ...]
main(sys.argv[1], sys.argv[2:])


