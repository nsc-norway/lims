# Script intended to be run in the Project Dashboard on analytes
# Sets the correct reagenet labels on Analytes based on a UDF 
# called "Index requested/used" on the associated Sample. 
# This allows a user to import samples with only the sequence, and
# later associate the sample with the correct reagent label. 

# use: python set-reagent-labels.py "Reagent category" {LIMS IDs}
# The first argument is the name of a reagent category.
# Lims IDs reperesents any number of Analyte LIMS IDs.

from genologics.lims import *
from genologics import config
from collections import defaultdict
import sys

def main(category, analyte_ids):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

    analytes = [Artifact(lims, id=analyte_id) for analyte_id in analyte_ids]
    sequences = set(ana.samples[0].udf['Index requested/used'] for ana in analytes)

    reagents = dict(
            (rt.sequence, rt) 
            for rt in lims.get_reagent_types() 
            if rt.category==category
        )

    if not sequences.issubset(set(reagents.keys())):
        raise ValueError("Not all sequences are available in category")

    for ana in analytes:
        sequence = ana.samples[0].udf['Index requested/used']
        sequences.add(sequence)
        ana.reagent_labels.clear()
        ana.reagent_labels.add(reagents[sequence].name)
        ana.put()


main(sys.argv[1], sys.argv[2:])
