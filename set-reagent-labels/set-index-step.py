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

def get_all_reagent_types():
    """Load all reagent types with name only, from the API resource.
    (this is a lot faster than getting the full representations one by
    one)""" 
    # Using a loop similar to Lims._get_instances()
    reagent_types = defaultdict(set)
    root = lims.get("reagenttypes")
    while root:
        for node in root.findall("reagent-type"):

            # add a reagent type to the search index, indexed by all words
            name = node.attrib['name']
            uri = node.attrib['uri']
            for token in (
                    tk.strip("()")
                    for tk in name.split(" ")
                    if tk != ""
                    ):
                reagent_types[tk].add(uri)
                
        node = root.find('next-page')
        root = None
        if not node is None:
            root = self.get(node.attrib['uri'])

    return reagent_types


def get_candidates_per_analyte(analytes, reagents):
    # Category indexes: a list for each category. Dict values are lists
    # of indexes.
    category_indexes = {}
    candidate_categories = set()

    analyte = analytes[0]
    sequence = analyte.samples[0].udf['Index requested/used']
    for token, reagent_uri in reagents[sequence]:
        reagent = Reagent(lims, id=reagent_uri)
        candidate_categories.add(reagent.category)
        category_indexes[reagent.category].append(reagent.name)

    for analyte in analytes[1:]:
        sequence = analyte.samples[0].udf['Index requested/used']
        candidates_not_seen = set(candidate_categories)
        for token, reagent_uri in reagents[sequence]:
            reagent = Reagent(lims, id=reagent_uri)
            if reagent.category in candidate_categories:
                candidates_not_seen.remove(reagent.category)

    


def select_indexes(analytes, category, search_mode):



def main(process_id, category):
    process = Process(lims, id=process_id)

    reagents = get_all_reagent_types() 

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

