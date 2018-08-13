# Runs on a dedicated "Set index" protocol step. 
# Supports different modes of operation:
# - Index from category (search mode for partial match)
# - Exact match mode
# - Auto-select category indexes

from genologics.lims import *
from genologics import config
from collections import defaultdict
import sys
import indexes

CATEGORY_UDF = "Index category (prepared libraries)"
SAMPLE_INDEX_UDF = "Index requested/used"

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

def reverse_complement(seq):
    complement={'A':'T', 'C':'G', 'G':'C', 'T':'A'}
    return "".join(reversed([complement[c] for c in seq]))

def main(process_id):
    """Assign reagents based on available reagent types, the Index requested/used UDF,
    and the specified category. If category is not given, any category could be used.
    """
    process = Process(lims, id=process_id)

    reagents = indexes.get_all_reagent_types() 
    analytes = process.all_inputs(unique=True)

    # Cache all analytes and samples
    analytes = lims.get_batch(analytes)
    lims.get_batch(analyte.samples[0] for analyte in analytes)
    try:
        category = process.udf[CATEGORY_UDF]
    except KeyError:
        category = None

    split_indexes_1 = [a.samples[0].udf[SAMPLE_INDEX_UDF].replace('+','-').split("-") for a in analytes]
    split_indexes = [map(lambda i: i.strip(" \t\xca\xa0\xc2"), ixs) for ixs in split_indexes_1]
    analyte_names = [a.name for a in analytes]

    if process.udf.get('Reverse complement index1'):
        split_indexes = [[reverse_complement(i[0])] + i[1:] for i in split_indexes]
    if process.udf.get('Reverse complement index2'):
        split_indexes = [i[0:1] + [reverse_complement(i[1])] for i in split_indexes]
    if process.udf.get('Swap index1 and index2'):
        split_indexes = [reversed(i) for i in split_indexes]

    allow_multi_match = process.udf.get('Allow multiple matching index categories', False)

    index_analyte = zip(["-".join(i) for i in split_indexes], analyte_names)
    try:
        if category == "Auto-detect":
            category, result = indexes.get_reagents_auto_category(reagents, index_analyte, allow_multi_match=True)
        else:
            result = indexes.get_reagents_for_category(reagents, index_analyte, category)
    except indexes.ReagentError as e:
        print str(e)
        sys.exit(1)

    process.udf[CATEGORY_UDF] = category
    process.put()

    # Assign the indexes
    for analyte, reagent_name in zip(analytes, result):
        sequence = analyte.samples[0].udf[SAMPLE_INDEX_UDF]
        analyte.reagent_labels.clear()
        analyte.reagent_labels.add(reagent_name)

    lims.put_batch(analytes)

    print "Successfully set the indexes"



main(sys.argv[1])

