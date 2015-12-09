import sys
import itertools
from openpyxl import load_workbook
import StringIO
import requests
import datetime
from genologics.lims import *
from genologics import config

# Import Excel file used for qPCR analysis

def main(process_id, file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    result_file_art = Artifact(lims, id=file_id)
    file_data = None
    try:
        if len(result_file_art.files) == 1:
            file_data = result_file_art.files[0].download()
    except requests.exceptions.HTTPError:
        pass

    if file_data is None:
        print "Could not access the result file, check that it has been uploaded"
        sys.exit(1)

    swl_io_obj = StringIO.StringIO(file_data)
    wb = load_workbook(swl_io_obj, data_only=True)
    results_sheet = wb['QC og  Konsentrasjon']
    
    values = [
            (row, results_sheet['Q%d' % (row,)], results_sheet['R%d' % (row,)])
            for row in xrange(74, 123)
            ]

    process_ios = dict((i['uri'].id, o['uri'].id) for i, o in process.input_output_maps if o['output-generation-type'] == "PerInput")
    process_inputs = set(process_ios.keys())
    try:
        updates = [
                (row, Artifact(lims, id=process_ios[limsid.value]), molarity)
                for row, limsid, molarity in values
                if limsid.value
                ]
    except KeyError, e:
        print "The LIMS-ID", e.args[0], "is not known on this step."
        sys.exit(1)

    results_limsids = set(limsid.value for row, limsid, molarity in values if limsid.value)
    if results_limsids != process_inputs:
        print "Missing information for samples: ", ", ".join(process_inputs - results_limsids), "."
        sys.exit(1)

    try:
        lims.get_batch(artifact for row, artifact, limsid in updates)
    except requests.exceptions.HTTPError:
        report_missing((row, artifact) for row, artifact, limsid in updates)
        sys.exit(1)

    missing_molarity = []
    for row, artifact, molarity in updates:
        if molarity is not None:
            artifact.udf['Molarity'] = molarity.value
        else:
            missing_molarity.append((row, artifact))
    
    if missing_molarity:
        print "Missing molarity for samples: ",
        print ", ".join(
                "%s (row %d)" % (artifact.name.encode('utf-8'), row)
                for row, aritfact in missing_molarity
                )
        sys.exit(1)

    lims.put_batch(artifact for row, artifact, molarity in updates)


    
def report_missing(results):
    missing = []
    for row, artifact in results:
        try:
            artifact.get()
        except requests.exceptions.HTTPError:
            missing.append((row, artifact.id))
            
    print "The following LIMS-IDs do not exist:",
    print ", ".join("%s (row %d)" % (limsid, row) for row, limsid in missing)


main(*sys.argv[1:])

