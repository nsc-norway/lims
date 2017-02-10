import sys
import re
from genologics.lims import *
from genologics import config

# Script to generate a text file for Hamilton robot

def main(process_id, file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    outputs = dict((o.location[1], o) for o in process.all_outputs(unique=True, resolve=True))
    container_0 = outputs.values()[0].location[0]
    assert all(o.location[0] == container_0 for o in outputs.values())

    lims.get_batch(o.samples[0] for o in outputs.values())

    with open(file_id + "-HamiltonSamplePlate.txt", "w") as f:
        f.write("""Version  2       \r\nID  Diag--      \r\nAssay   \r\nNextera Rapid Capture Enrichment        \r\nIndexReads  2       \r\nIndexCycles 8       \r\n""")
        for row in 'ABCDEFGH':
            for col in range(1, 13):
                well_label = "%s%02d" % (row, col)
                lims_well_label = "%s:%d" % (row, col)
                output = outputs.get(lims_well_label)
                if output:
                    f.write("{0}{1:02}\t{2}\t{3}\t{4}\r\n".format(
                        row, col, output.name, i7, i5
                        ))
                else:
                    f.write("{0}{1:02}\t{2}\t{3}\t{4}\r\n".format(
                        row, col, "", "", ""
                        ))
        f.write("[AssaySettings]            \r\n")


# Use:  main PROCESS_ID FILE_ID
main(sys.argv[1], sys.argv[2])

