import sys
import itertools
from openpyxl import load_workbook
import StringIO
import requests
from genologics.lims import *
from genologics import config

# SwissLab data import script

# Use:
# python swisslab-import.py PROCESS-ID SWL-FILE
# Arguments:
#  PROCESS-ID: LIMS-ID of a process on which this script is run.
#  SWL-FILE:   LIMS-ID of Artifact object for Excel file

GENERAL_COLUMNS = {
        "Test SWL Diag": str,
        "Referral reason Diag": str,
        "Archive position Diag": str,
        "Sample conc. (ng/ul)": float,
        "Analysis registered Diag": str,
        "Gene panel Diag": str,
        "Kit version Diag": str,
        "Analysis type Diag": str
        }

TRIO_COLUMNS = {
        "Family number Diag": str,
        "Relation Diag": str,
        "Sex Diag": str
        }

ALL_COLUMNS = frozenset(GENERAL_COLUMNS.keys() + TRIO_COLUMNS.keys())

def get_swl_data(filename):
    """Parsing of sample information table in Excel format.
    
    Returns a dict indexed by sample name, where each value is a list 
    of (udfname, udfvalue) tuples.
    { sample name => [ (udfname, udfvalue), ... ] }
    """
    try:
        wb = load_workbook(filename, data_only=True)
    except IOError:
        print "Cannot read the SwissLab file, make sure it is in Excel format"
        sys.exit(1)

    ws = wb['Samples']

    assert ws['A1'].value == "Sample/Name"
    # Get { header name => column index }
    headers = {}
    for i in itertools.count(2):
        h = ws.cell(column=i, row=1).value
        if h:
            if h in ALL_COLUMNS:
                headers[h] = i
        else:
            break

    missing = ALL_COLUMNS - frozenset(headers.keys())
    if missing:
        print "Missing the following columns in the Excel file:", ",".join(missing)
        sys.exit(1)

    data = {}
    for row in itertools.count(2):
        sample_name = ws.cell(column=1, row=row).value
        if sample_name:

            sample_data = get_all_fields(
                    sample_name,
                    ws, row, headers,
                    GENERAL_COLUMNS, 
                    True
                    )

            trio_fields_required = any(
                    val == "trio" and name == "Analysis type Diag"
                    for name, val in sample_data
                    )
            sample_data += get_all_fields(
                    sample_name,
                    ws, row, headers,
                    TRIO_COLUMNS,
                    trio_fields_required
                    )
            data[sample_name] = sample_data
        else:
            break

    return data


def get_all_fields(sample_name, ws, row, headers, columns, required):
    """Get a list of tuples, one for each column in the columns parameter."""
    result = []
    for col, value_type in columns.items():
        v = ws.cell(column=headers[col], row=row).value
        if not v is None:
            try:
                result.append((col, value_type(v)))
            except ValueError:
                print "Cannot convert '" +  str(v) + "' to a", value_type,\
                        "for sample", sample_name, ", column", col
                sys.exit(1)
        elif required:
            print "Missing required value for '", col, "' for sample", sample_name
            sys.exit(1)
    return result
            

def main(process_id, swl_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

    swl_file_art_obj = Artifact(lims, id=swl_file_id)
    if len(swl_file_art_obj.files) == 1:
        swl_io_obj = StringIO.StringIO(swl_file_art_obj.files[0].download())
    else:
        print "Could not access the SwissLab file, check that it has been uploaded"
        sys.exit(1)

    swisslab_data = get_swl_data(swl_io_obj)

    process = Process(lims, id=process_id)
    inputs = process.all_inputs(unique=True, resolve=True)
    assert all(len(input.samples) == 1 for input in inputs)
    samples = lims.get_batch(input.samples[0] for input in inputs)

    for sample in samples:
        try:
            fields = swisslab_data[sample.name]
        except KeyError:
            print "Failed trying to look up sample", sample.name, "in the provided table"
            sys.exit(1)

        for udfname, udfval in fields:
            sample.udf[udfname] = udfval

    lims.put_batch(samples)
    print "Imported data for", len(samples), "samples"


main(*sys.argv[1:])

