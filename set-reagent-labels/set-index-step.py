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

    if category == "Auto-detect":
        category, result = indexes.get_reagents_auto_category(reagents, analytes)
    else:
        result = indexes.get_reagents_for_category(reagents, analytes, category)

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

