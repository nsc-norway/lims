import sys

# Based on Quant-iT multi input, but with thresholds

from genologics import config
from genologics.lims import *

import numpy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pylab as plt

from xlrd import open_workbook

ROWS = ["A","B","C","D","E","F","G","H"]
ROW_SPACING = 3
STANDARD_VOLUME = 10.0

def parse_spectramax_result_file(text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Plate:\t"):
            break
    else:
        raise ValueError("Line starting with 'Plate:' not found.")

    plate_id = line.split("\t")[1]
    rows = [row.split("\t")[2:] for row in lines[i+2:i+10]]
    data = {}
    for row_label, row in zip("ABCDEFGH", rows):
        for col_label, cell in zip(range(1, 13), row):
            # We sometimes get files with a decimal comma. I have never seen 
            # a comma thousands separator, so here we go, hoping for the best
            # float() will fail if there are multiple dots after this.
            cell = cell.replace('"', '').replace(",", ".")
            data["{0}:{1}".format(row_label, col_label)] = float(cell)
    return (plate_id, data)


def parse_synergy_result_file(content):
    book = open_workbook(file_contents=content, formatting_info=False )
    # There is only one worksheet in the file
    sheet = book.sheet_by_index(0)
    for row in xrange(0, 1000):
        if sheet.cell(row, 0).value == "Results":
            break

    first_row = row+4
    assert all(sheet.cell(first_row-1, 2+i).value == i+1 for i in range(12)), "Unexpected result file format (col not as expected)"
    assert all(sheet.cell(first_row+i*ROW_SPACING, 1).value == c for i, c in enumerate(ROWS)), "Unexpected result file format (row not as expected)"

    data = {}
    for irow, row in enumerate(ROWS):
        for col in range(1,13):
            data["{0}:{1}".format(row, col)] = sheet.cell(first_row+(irow*ROW_SPACING), col+1).value
    return data


def make_plot(sample_volume, x, y, slope, graph_file_id):
    plt.ioff()
    f = plt.figure()
    plt.plot(x, y, 'ro')
    plt.plot(x, [xi*slope for xi in x])
    plt.xlim(x[0] - 5, x[-1] + 5)
    plt.xlabel("Concentration x {0} (ng/uL)".format(STANDARD_VOLUME / sample_volume))
    plt.ylabel("Fluorescence counts")
    plt.savefig(graph_file_id + ".png")


def main(file_format, process_id, graph_file_id, sample_volume, input_file_ids):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    lims.get_batch(process.all_inputs() + process.all_outputs())
    
    standards_concs = [float(v) for v in process.udf['Concentrations of standards (ng/uL)'].split(",")]
    assert len(standards_concs) == 8, "Invalid number of standards"

    result_files = set([o['uri'] for i,o in process.input_output_maps if o['output-generation-type'] == "PerInput"])
    assert len(result_files) > 0, "No output artifacts found"
    output_containers = sorted(set(rf.container for rf in result_files), key=lambda cont: cont.id)

    assert len(input_file_ids) >= len(output_containers),\
            "This step is only configured for {0} plates".format(len(input_file_ids))

    container_data = {}
    for index, container in enumerate(["STD"] + output_containers):
        try:
            file_obj = Artifact(lims, id=input_file_ids[index]).files[0]
        except IndexError:
            print "No input file for plate number", index
            sys.exit(1)
        try:
            if file_format == "SpectraMax":
                plate_id, container_data[container] = parse_spectramax_result_file(file_obj.download().decode("utf-16"))
            elif file_format == "Synergy":
                container_data[container] = parse_synergy_result_file(file_obj.download())
            else:
                raise RuntimeError("Format '" + str(file_format) + "' is not supported")
        except ValueError as e:
            print "Result file {0} has invalid format ({1}).".format(index, e)
            sys.exit(1)

    standards_col = process.udf['Column in standards plate']

    # Concentrations (x)
    scaled_concs = numpy.array([sv * STANDARD_VOLUME / sample_volume for sv in standards_concs])

    # Counts (y)
    standards_values = [container_data["STD"]["{0}:{1}".format(row, standards_col)] for row in ROWS]
    std0_value = standards_values[0]
    process.udf['Std0 value'] = std0_value
    shifted_standards_values = numpy.array([c - std0_value for c in standards_values])
    
    stdcurve_fn = lambda x, a: a*x # y=ax
    xdata = numpy.matrix([scaled_concs]).T
    ydata = numpy.array(shifted_standards_values)

    slopes, _, _, _ = numpy.linalg.lstsq(xdata, ydata)
    slope = slopes[0]

    # Calculate R^2: we need the "total" sum of squares rel to mean, and residuals
    mean = numpy.mean(shifted_standards_values)
    totalsum2s = ((shifted_standards_values - mean)**2).sum()
    residualsum2s = ((shifted_standards_values - slope*scaled_concs)**2).sum()

    process.udf['R^2'] = 1 - residualsum2s / totalsum2s
    standard_fail = process.udf['R^2'] < process.udf.get('QC threshold R^2', 0)

    qcfail_count = 0

    for o in result_files:
        conc = (container_data[o.location[0]][o.location[1]] - std0_value) / slope
        if conc < process.udf.get('QC threshold Concentration', 0) or standard_fail:
            qcfail_count += 1
            o.qc_flag = "FAILED"
        else:
            o.qc_flag = "PASSED"
        o.udf['Concentration'] = conc

    # Plot the data and the curve
    # Intercept parameter is now fixed at 0
    make_plot(sample_volume, scaled_concs, shifted_standards_values, slope, graph_file_id)
    lims.put_batch(result_files)

    process.put()

    if standard_fail:
        print "Standard curve R^2 failed, all samples marked as QC fail."
    elif qcfail_count:
        print "Marked", qcfail_count, "samples as failed due to low concentrations."
    else:
        print "Successfully imported data from", len(container_data), "file(s)."


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print "Need at least four parameters! File format, Process ID, graph_file_id, sample_volume, input_file_id(s)."
        sys.exit(1)
    elif len(sys.argv) >= 5:
        main(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5:])

