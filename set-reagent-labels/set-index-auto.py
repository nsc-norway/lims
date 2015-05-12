# See also set-reagent-labels.py for comments.
# This script attempts to determine the index type automatically.

from genologics.lims import *
from genologics import config
from collections import defaultdict
import sys

def main(analyte_ids):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    analytes = [Artifact(lims, id=analyte_id) for analyte_id in analyte_ids]

    input_indexes = set()
    for ana in analytes:
        sequence = ana.samples[0].udf['Index requested/used']
        input_indexes.add(sequence)

    reagent_types = lims.get_reagent_types()

    cat_indexes = defaultdict(set)
    for rt in reagent_types:
        if rt.index_sequence:
            cat_indexes[rt.category].add(rt.index_sequence)

    categories = []
    for cat_name, indexset in cat_indexes.items():
        if indexset.issuperset(input_indexes):
            categories.append(cat_name)

    if len(categories) == 1:
        reagents = dict(
                (rt.index_sequence, rt) 
                for rt in lims.get_reagent_types() 
                if rt.category==categories[0]
            )

        for ana in analytes:
            sequence = ana.samples[0].udf['Index requested/used']
            ana.reagent_labels.add(reagents[sequence].name)
            ana.put()

    elif categories:
        raise RuntimeError("Multiple categories match: " + ", ".join(categories))
    else:
        raise RuntimeError("No category found")


main(sys.argv[1:])

