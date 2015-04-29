import sys
from genologics.lims import *
from genologics import config
import printtable

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    outputs = process.all_outputs(unique=True)

    data = [["Sample", "Container", "Well", "Index"]]
    for o in sorted((o for o in outputs if o.type == "Analyte"), key=lambda x: (x.location[0], reversed(x.location[1]))):
        data.append([o.name, o.location[0].name, o.location[1], next(iter(o.reagent_labels))])
    printtable.print_table("Indexes for project " + o.samples[0].project.name, data)



main(sys.argv[1])

