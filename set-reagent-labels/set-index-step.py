# Runs on a dedicated "Set index" protocol step. 
# Supports different modes of operation:
# - Index from category (search mode for partial match)
# - Exact match mode
# - Auto-select category indexes

from genologics.lims import *
from genologics import config
from collections import defaultdict
import sys

CATEGORY_UDF = "Index category (prepared libraries)"
SAMPLE_INDEX_UDF = "Index requested/used"

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

def get_all_reagent_types():
    """Load all reagent types with name only, from the API resource.
    (this is a lot faster than getting the full representations one by
    one)""" 
    # Using a loop similar to Lims._get_instances()
    reagent_types = defaultdict(set)
    root = lims.get(lims.get_uri("reagenttypes"))
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
                reagent_types[token].add(uri)
                
        node = root.find('next-page')
        root = None
        if not node is None:
            root = lims.get(node.attrib['uri'])

    return reagent_types


def get_reagents_auto_category(reagents, analytes, sequence_match=False):
    category_indexes = {}
    candidate_categories = set()
    ana_no_match = [] # list of analytes with no indexes at all
    not_in_category = []

    # Add all possible categories -- use categories for the first  analyte
    analyte = analytes[0]
    ana_match_string = analyte.samples[0].udf[SAMPLE_INDEX_UDF]
    for reagent_uri in reagents[ana_match_string]:
        reagent = ReagentType(lims, uri=reagent_uri) 
        candidate_categories.add(reagent.category)
        category_indexes[reagent.category] = []

    # 2. Process all analytes including the first one
    for analyte in analytes:
        new_candidates = set()
        ana_match_string = analyte.samples[0].udf[SAMPLE_INDEX_UDF]
        analyte_reagents = reagents[ana_match_string]
        if not analyte_reagents:
            ana_no_match.append(analyte.name)
        for reagent_uri in reagents[ana_match_string]:
            reagent = ReagentType(lims, uri=reagent_uri)
            if not sequence_match or reagent.index_sequence == ana_match_string:
                if reagent.category in candidate_categories:
                    new_candidates.add(reagent.category)
                    category_indexes[reagent.category].append(reagent.name)
        candidate_categories = new_candidates

    if ana_no_match:
        print "Samples with no match at all: ", ", ".join(ana_no_match)
        sys.exit(1)
    elif len(candidate_categories) == 1:
        cat = next(iter(candidate_categories))
        return cat, category_indexes[cat]
    elif not candidate_categories:
        print "No reagent category has all the given indexes"
        sys.exit(1)
    elif len(candidate_categories) > 1:
        print "Multiple categories match: ", ", ".join(candidate_categories)
        sys.exit(1)


def get_reagents_for_category(reagents, analytes, category, sequence_match=False):
    match_reagents = []
    ana_no_match = [] # list of analytes with no indexes at all

    # 2. Process all analytes including the first one
    for analyte in analytes:
        ana_match_string = analyte.samples[0].udf[SAMPLE_INDEX_UDF]
        analyte_reagents = reagents[ana_match_string]
        match = False
        for reagent_uri in reagents[ana_match_string]:
            reagent = ReagentType(lims, uri=reagent_uri)
            if not sequence_match or reagent.index_sequence == ana_match_string:
                if reagent.category == category:
                    match_reagents.append(reagent.name)
                    match = True
        if not match:
            ana_no_match.append(analyte.name)


    if ana_no_match:
        print "No matching reagent type found for samples: ", ", ".join(ana_no_match)
        sys.exit(1)
    else:
        return match_reagents


def main(process_id):
    """Assign reagents based on available reagent types, the Index requested/used UDF,
    and the specified category. If category is not given, any category could be used.
    """
    process = Process(lims, id=process_id)

    reagents = get_all_reagent_types() 
    analytes = process.all_inputs()

    try:
        category = process.udf[CATEGORY_UDF]
    except KeyError:
        category = None

    if category == "Auto-detect":
        category, result = get_reagents_auto_category(reagents, analytes)
    else:
        result = get_reagents_for_category(reagents, analytes, category)

    process.udf[CATEGORY_UDF] = category
    process.put()

    # Assign the indexes
    for analyte, reagent_name in zip(analytes, result):
        sequence = analyte.samples[0].udf[SAMPLE_INDEX_UDF]
        analyte.reagent_labels.clear()
        analyte.reagent_labels.add(reagent_name)
        analyte.put()

    print "Successfully set the indexes"



main(sys.argv[1])

