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

SAMPLE_INDEX_UDF = "Index requested/used"

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)


def main(analyte_ids):
    """Assign reagents based on available reagent types, the Index requested/used UDF,
    and automatic detection of category.
    """
    reagents = indexes.get_all_reagent_types() 
    analytes = [Artifact(lims, id=analyte_id) for analyte_id in analyte_ids]

    # Cache all analytes and samples
    analytes = lims.get_batch(analytes)
    lims.get_batch(analyte.samples[0] for analyte in analytes)
    index_analyte = [(a.samples[0].udf[SAMPLE_INDEX_UDF].strip(" \t"), a.name) for a in analytes]

    try:
        category, result = indexes.get_reagents_auto_category(reagents, index_analyte)
    except indexes.ReagentError as e:
        print e.message
        sys.exit(1)

    # Assign the indexes
    for analyte, reagent_name in zip(analytes, result):
        sequence = analyte.samples[0].udf[SAMPLE_INDEX_UDF]
        analyte.reagent_labels.clear()
        analyte.reagent_labels.add(reagent_name)

    lims.put_batch(analytes)

    print "Successfully set the indexes"


main(sys.argv[1:])

