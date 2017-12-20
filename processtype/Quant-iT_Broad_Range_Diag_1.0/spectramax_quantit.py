import sys

from genologics import config
from genologics.lims import *

from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pylab as plt

ROWS = ["A","B","C","D","E","F","G","H"]
ROW_SPACING = 3
DEFAULT_SAMPLE_VOLUME = 1.0
STANDARD_VOLUME = 10.0

def parse_result_file(text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Plate:\t"):
            break
    else:
        raise ValueError("Line starting with 'Plate:' not found.")

    rows = [row.split("\t")[2:] for row in lines[i+2:i+10]]
    data = {}
    for row_label, row in zip("ABCDEFGH", rows):
        for col_label, cell in zip(range(1, 13), row):
            # We sometimes get files with a decimal comma. I have never seen 
            # a comma thousands separator, so here we go, hoping for the best
            # float() will fail if there are multiple dots after this.
            cell = cell.replace(",", ".")
            data["{0}:{1}".format(row_label, col_label)] = float(cell)
    return data


def make_plot(sample_volume, x, y, intercept, slope, graph_file_id):
    plt.ioff()
    f = plt.figure()
    plt.plot(x, y, 'ro')
    plt.plot(x, [xi*slope + intercept for xi in x])
    plt.xlim(x[0] - 5, x[-1] + 5)
    plt.xlabel("Concentration x {0} (ng/uL)".format(STANDARD_VOLUME / sample_volume))
    plt.ylabel("Fluorescence counts")
    plt.savefig(graph_file_id + ".png")


def main(process_id, graph_file_id, sample_volume):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    lims.get_batch(process.all_inputs() + process.all_outputs())
    
    standards_concs = [float(v) for v in process.udf['Concentrations of standards (ng/uL)'].split(",")]
    assert len(standards_concs) == 8, "Invalid number of standards"

    datafiles = next((
            o['uri']
            for i,o in process.input_output_maps
            if o['output-generation-type'] == "PerAllInputs" and o['uri'].name == "Quant-iT results"
            )).files
    if not datafiles:
        print "No result file found"
        sys.exit(1)

    try:
        data = parse_result_file(datafiles[0].download().decode("utf-16"))
    except ValueError, e:
        print "Result file has invalid format (" + str(e) + ")."
        sys.exit(1)

    standards_values = [data["{0}:{1}".format(row, 1)] for row in ROWS]
    print standards_values
    scaled_concs = [sv * STANDARD_VOLUME / sample_volume for sv in standards_concs]

    slope, intercept, r_value, p_value, std_err = stats.linregress(scaled_concs, standards_values)

    process.udf['R^2'] = r_value**2

    result_files = set([o['uri'] for i,o in process.input_output_maps if o['output-generation-type'] == "PerInput"])
    assert len(set(rf.container for rf in result_files)) == 1, "This script can only read one plate at a time"

    for o in result_files:
        conc = (data[o.location[1]] - intercept) / slope
        o.udf['Concentration'] = conc


    make_plot(sample_volume, scaled_concs, standards_values, intercept, slope, graph_file_id)
    lims.put_batch(result_files)

    process.put()
    print "Successfully imported data from", datafiles[0].original_location, "."


if __name__ == "__main__":
    if len(sys.argv) == 3:
        main(sys.argv[1], sys.argv[2], DEFAULT_SAMPLE_VOLUME)
    elif len(sys.argv) >= 4:
        main(sys.argv[1], sys.argv[2], float(sys.argv[3]))
    else:
        print("Incorrect usage (see script)")
        sys.exit(1)

