# Runs on a dedicated "Set index" protocol step. 
# Supports different modes of operation:
# - Index from category (search mode for partial match)
# - Exact match mode
# - Auto-select category indexes

from genologics.lims import *
from genologics import config
from collections import defaultdict
import sys

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

def get_all_candidates():
    """Load all reagent types with name only, from the API resource.
    (this is a lot faster than doing them one by one)"""
    return lims.get(params=)

def get_candidates_per_analyte(analytes, candidates):



def select_indexes(analytes, category, search_mode):



def main(process_id, category):
    process = Process(lims, id=process_id)

    

    print "Getting a list of indexes for cat.", category, "..."
    reagents = 
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

