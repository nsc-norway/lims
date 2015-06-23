# use: python set-index-step.py {Process-ID} "Reagent category"

from genologics.lims import *
from genologics import config
from collections import defaultdict
import sys

def main(process_id, category):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    print "Getting a list of indexes for cat.", category, "..."
    reagents = dict(
            (rt.index_sequence, rt) 
            for rt in lims.get_reagent_types() 
            if rt.category==category
        )

    analytes = process.all_inputs()
    print "Checking the requested indexes..."
    sequences = set(ana.samples[0].udf['Index requested/used'] for ana in analytes)

    if not sequences.issubset(set(reagents.keys())):
        print "Requested index not in category for samples: ", ", ".join(
                ana.samples[0].name for ana in analytes
                if not ana.samples[0].udf['Index requested/used'] in reagents.keys()
                )
        sys.exit(1)

    print "Assigning the indexes..."
    for ana in analytes:
        sequence = ana.samples[0].udf['Index requested/used']
        sequences.add(sequence)
        ana.reagent_labels.clear()
        ana.reagent_labels.add(reagents[sequence].name)
        ana.put()

    print "Successfully set the indexes"


main(sys.argv[1], sys.argv[2])

