# Library for setting indexes

import sys
import re
import urlparse

from genologics.lims import *
from genologics import config
from collections import defaultdict

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

BLACKLIST = set()

if re.search(r"/cees-lims.sequencing.uio.no[:/]", config.BASEURI):
    # Deleted index IDs
    BLACKLIST = set([1301] + range(121, 145))
elif re.search(r"/ous-lims.ous.nsc.local[:/]", config.BASEURI):
    # Deleted index IDs
    # Second term after | is a result of a botched import of nextera v2 indexes Nxx-Sxx
    BLACKLIST = set(range(709, 721)) | (set(range(1692,1793)) - set(range(1697,1793,8)))
    BLACKLIST |= set(501, 597) | set(613,709) #SureSelect XT2 8bp indexes (replaced)
elif re.search(r"/dev-lims.ous.nsc.local[:/]", config.BASEURI):
    BLACKLIST = set(range(501, 597))

def get_all_reagent_types():
    """Load all reagent types with name only, from the API resource.
    (this is a lot faster than getting the full representations one by
    one).
    
    Breaks the name into space-separated tokens, also removing brackets
    () at the beginning and end of the tokens. Then returns a dict indexed
    by the token, where the values are sets of reagent types matching that
    token. {token => (reagent1, reagent2, ...)}
    
    Example: The name "AD005 (ACAGTG)" becomes two tokens: AD005 
    and ACAGTG.
    """ 
    # Using a loop similar to Lims._get_instances()
    reagent_types = defaultdict(set)
    root = lims.get(lims.get_uri("reagenttypes"))
    while root:
        for node in root.findall("reagent-type"):

            # add a reagent type to the search index, indexed by all words
            name = node.attrib['name']
            uri = node.attrib['uri']
            # Get ID, copy/paste from genologics lib
            parts = urlparse.urlsplit(uri)
            id = int(parts.path.split('/')[-1])
            if not id in BLACKLIST:
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


def get_reagents_auto_category(reagents, index_analyte, sequence_match=False):
    category_indexes = {}
    candidate_categories = set()
    ana_no_match = [] # list of analytes with no indexes at all
    not_in_category = []

    # Add all possible categories -- use categories for the first  analyte
    ana_match_string = index_analyte[0][0]
    for reagent_uri in reagents[ana_match_string]:
        reagent = ReagentType(lims, uri=reagent_uri) 
        candidate_categories.add(reagent.category)
        category_indexes[reagent.category] = []

    # 2. Process all analytes including the first one
    for index, analyte_name in index_analyte:
        new_candidates = set()
        ana_match_string = index
        analyte_reagents = reagents[ana_match_string]
        if not analyte_reagents:
            ana_no_match.append(analyte_name)
        for reagent_uri in reagents[ana_match_string]:
            reagent = ReagentType(lims, uri=reagent_uri)
            if not sequence_match or reagent.sequence == ana_match_string:
                if reagent.category in candidate_categories:
                    if reagent.category in new_candidates:
                        print "Ambiguous match for sample", analyte_name, ": in category", reagent.category,\
                                "the specified index matches multiple reagent types:", reagent.name, "and",\
                                category_indexes[reagent.category][-1]
                        sys.exit(-1)
                    else:
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


def get_reagents_for_category(reagents, index_analyte, category, sequence_match=False):
    match_reagents = []
    ana_no_match = [] # list of analytes with no indexes at all

    # 2. Process all analytes including the first one
    for index, analyte_name in index_analyte:
        ana_match_string = index
        analyte_reagents = reagents[ana_match_string]
        match = False
        for reagent_uri in reagents[ana_match_string]:
            reagent = ReagentType(lims, uri=reagent_uri)
            if not sequence_match or reagent.sequence == ana_match_string:
                if reagent.category == category:
                    if match:
                        print "Ambiguous match for sample", analyte_name, ": specified index "\
                                "matches multiple reagent types:", reagent.name, "and",\
                                match_reagents[-1]
                        sys.exit(-1)
                    else:
                        match_reagents.append(reagent.name)
                        match = True
        if not match:
            ana_no_match.append(analyte_name)


    if ana_no_match:
        print "No matching reagent type found for samples: ", ", ".join(ana_no_match)
        sys.exit(1)
    else:
        return match_reagents



