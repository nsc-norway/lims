# Library for setting indexes

# NOTE: This file is also used from ../proj-imp/, via a symlink

import re

from genologics.lims import *
from genologics import config
from collections import defaultdict

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

class ReagentError(Exception):
    pass


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
                        raise ReagentError("Ambiguous match for sample" + analyte_name + ": in category" + reagent.category +\
                                "the specified index matches multiple reagent types:" + reagent.name + "and" +\
                                category_indexes[reagent.category][-1])
                    else:
                        new_candidates.add(reagent.category)
                        category_indexes[reagent.category].append(reagent.name)
        candidate_categories = new_candidates

    if ana_no_match:
        raise ReagentError("Samples with no match at all: " + ", ".join(ana_no_match))
    elif len(candidate_categories) == 1:
        cat = next(iter(candidate_categories))
        return cat, category_indexes[cat]
    elif not candidate_categories:
        raise ReagentError("No reagent category has all the given indexes")
    elif len(candidate_categories) > 1:
        raise ReagentError("Multiple categories match: " + ", ".join(candidate_categories))


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
                        raise ReagentError("Ambiguous match for sample" +  analyte_name + ": specified index "\
                                "matches multiple reagent types: " + reagent.name +  " and " +\
                                match_reagents[-1])
                    else:
                        match_reagents.append(reagent.name)
                        match = True
        if not match:
            ana_no_match.append(analyte_name)


    if ana_no_match:
        raise ReagentError("No matching reagent type found for samples: " + ", ".join(ana_no_match))
    else:
        return match_reagents



