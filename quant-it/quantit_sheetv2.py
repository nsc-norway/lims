import sys

from genologics import config
from genologics.lims import *

from xlrd import open_workbook
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pylab as plt

ROWS = ["A","B","C","D","E","F","G","H"]
STANDARD_VOLUME = 10.0
SAMPLE_VOLUME = 1.0

def parse_result_file(content):
    book = open_workbook(file_contents=content, formatting_info=False )
    # There is only one worksheet in the file
    sheet = book.sheet_by_index(0)
    for row in xrange(0, 1000):
        if sheet.cell(row, 0).value == "Results":
            break

    first_row = row+4
    assert sheet.cell(first_row-1, 2).value == 1.0, "Unexpected result file format (col 1 not found; row={0})".format(first_row-1)
    assert sheet.cell(first_row, 1).value == "A", "Unexpected result file format (row A not found)"
    
    data = {}
    for irow, row in enumerate(ROWS):
        for col in range(1,13):
            data["{0}:{1}".format(row, col)] = sheet.cell(first_row+(irow*3), col+1).value
    return data


def make_plot(x, y, intercept, slope, graph_file_id):
    plt.ioff()
    f = plt.figure()
    plt.plot(x, y, 'ro')
    plt.plot(x, [xi*slope + intercept for xi in x])
    plt.xlim(x[0] - 5, x[-1] + 5)
    plt.xlabel("Concentration x {0} (ng/uL)".format(STANDARD_VOLUME / SAMPLE_VOLUME))
    plt.ylabel("Fluorescence counts")
    plt.savefig(graph_file_id + ".png")


def main(process_id, graph_file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    lims.get_batch(process.all_inputs() + process.all_outputs())
    
    standards_concs = [float(v) for v in process.udf['Concentrations of standards (ng/uL)'].split(",")]
    assert len(standards_concs) == 8, "Invalid number of standards"

    datafiles = next((
            o['uri']
            for i,o in process.input_output_maps
            if o['output-generation-type'] == "PerAllInputs" and o['uri'].name == "Quant-iT results (xls)"
            )).files
    if not datafiles:
        print "No result file found"
        sys.exit(1)

    data = parse_result_file(datafiles[0].download())

    standards_values = [data["{0}:{1}".format(row, 1)] for row in ROWS]
    scaled_concs = [sv * STANDARD_VOLUME / SAMPLE_VOLUME for sv in standards_concs]

    slope, intercept, r_value, p_value, std_err = stats.linregress(scaled_concs, standards_values)

    process.udf['Correlation coefficient (r)'] = r_value
    process.udf['Standard error'] = std_err

    result_files = set([o['uri'] for i,o in process.input_output_maps if o['output-generation-type'] == "PerInput"])
    assert len(set(rf.container for rf in result_files)) == 1, "Only one Quant-iT run is allowed"

    for o in result_files:
        conc = (data[o.location[1]] - intercept) / slope
        o.udf['Concentration'] = conc


    make_plot(scaled_concs, standards_values, intercept, slope, graph_file_id)
    lims.put_batch(result_files)

    process.put()
    print "Successfully imported data from", datafiles[0].original_location, "."


if __name__ == "__main__":
	main(sys.argv[1], sys.argv[2])
