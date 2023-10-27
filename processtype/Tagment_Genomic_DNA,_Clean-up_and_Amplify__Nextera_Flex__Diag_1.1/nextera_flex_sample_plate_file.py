import sys
import re
import datetime
from genologics.lims import *
from genologics import config

# Script to generate a text file for Hamilton robot
# Nextera

alpha = 'ABCDEFGH'

def main(process_id, file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    outputs = dict((o.location[1], o) for o in process.all_outputs(unique=True, resolve=True) if o.type == 'Analyte')
    container_0 = next(iter(outputs.values())).location[0]
    assert all(o.location[0] == container_0 for o in outputs.values())

    with open(file_id + "-HamiltonSamplePlate.txt", "w") as f:
        f.write("""Version\t2\r\nID\t{0}\r\nAssay\tTruSeq HT\r\nIndexReads\t2\r\nIndexCycles\t8\r\n""".format(datetime.date.today()))
        for row in alpha:
            for col in range(1, 13):
                well_label = "%s%02d" % (row, col)
                lims_well_label = "%s:%d" % (row, col)
                output = outputs.get(lims_well_label)
                if output:
                    try:
                        index_name = output.reagent_labels[0]
                    except:
                        print("Missing index information for", output.name, ", aborting.")
                        sys.exit(1)
                    try:
                        match = re.match(r"(\d\d[A-H]) .7\d\d-.5\d\d .*", index_name)
                        index_well = match.group(1)[2:] + match.group(1)[:2]
                    except:
                        try:
                            # Convert UDI plate to well position
                            match = re.match(r"(24UDI|UDI|UDP|IDT10_|IDT)(\d{4}) .*", index_name)
                            udi_nr = int(match.group(2))
                            colnr = ((udi_nr - 1) // 8) % 12
                            rownr = (udi_nr - 1) % 8
                            index_well = "%s%02d" % (alpha[rownr], colnr+1)
                        except:
                            print("Invalid index information for", output.name, " (unable to parse '" + index_name + "').")
                            sys.exit(1)
                    sample_id = output.samples[0].project.name + "." + output.name
                    f.write("{0}{1:02}\t{2}\t{3}\r\n".format(
                        row, col, sample_id, index_well
                        ))
                else:
                    f.write("{0}{1:02}\t\t\t\r\n".format(
                        row, col
                        ))
        f.write("[AssaySettings]            \r\n")

# Use:  main PROCESS_ID FILE_ID
main(sys.argv[1], sys.argv[2])

