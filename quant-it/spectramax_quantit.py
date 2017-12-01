import sys

from genologics import config
from genologics.lims import *

import numpy
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


def main(process_id, graph_file_id, sample_volume, input_file_ids):
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
    for index, container in enumerate(output_containers):
        try:
            file_obj = Artifact(lims, id=input_file_ids[index]).files[0]
        except IndexError:
            print "No input file for plate number", (index+1)
            sys.exit(1)
        try:
            container_data[container] = parse_result_file(file_obj.download().decode("utf-16"))
        except ValueError, e:
            print "Result file has invalid format (" + str(e) + ")."
            sys.exit(1)

    # Concentrations (x)
    scaled_concs = numpy.array([sv * STANDARD_VOLUME / sample_volume for sv in standards_concs])

    # Counts (y)
    first_container = output_containers[0]
    standards_values = [container_data[first_container]["{0}:{1}".format(row, 1)] for row in ROWS]
    std0_value = scaled_concs[0]
    process.udf['Std0 value'] = std0_value
    shifted_values = numpy.array([c - std0_value for c in scaled_concs])
    
    stdcurve_fn = lambda x, a: a*x # y=ax
    xdata = numpy.matrix([scaled_concs]).T
    ydata = numpy.array(shifted_values)

    slopes, _, _, _ = numpy.linalg.lstsq(xdata, ydata)
    slope = slopes[0]

    # Calculate R^2: we need the "total" sum of squares rel to mean, and residuals
    mean = numpy.mean(shifted_values)
    totalsum2 = ((shifted_values - mean)**2).sum()
    residualsum2 = ((shifted_values - slope*scaled_concs)**2).sum()

    process.udf['R^2'] = 1 - residualsum2 / totalsum2

    for o in result_files:
        if o.location[0] == first_container and o.location[1].endswith(":1"):
            print "Detected a sample in the position", o.location[1], "which should be a standard."
            sys.exit(1)
        conc = (container_data[o.location[0]][o.location[1]]) / slope
        o.udf['Concentration'] = conc

    # Plot the data and the curve
    # Intercept parameter is now fixed at 0
    make_plot(sample_volume, scaled_concs, standards_values, 0, slope, graph_file_id)
    lims.put_batch(result_files)

    process.put()
    print "Successfully imported data from", len(container_data), "file(s)."


if __name__ == "__main__":
    if len(sys.argv) == 3:
        print "Usage with two parameters is no longer supported! The step configuration should be updated."
        sys.exit(1)
    elif len(sys.argv) >= 4:
        main(sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4:])
    else:
        print("Incorrect usage (see script)")
        sys.exit(1)

