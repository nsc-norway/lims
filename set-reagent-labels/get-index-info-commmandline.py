# Search for index sequence and print it if found

from genologics.lims import *
from genologics import config
from collections import defaultdict
import sys
import argparse

import indexes

parser = argparse.ArgumentParser(description="Get indexes from LIMS database based on sequences given on command line.")
parser.add_argument("--category", type=str, help="Specify reagent category (default is to auto-detect).")
parser.add_argument("--unique-match", type=bool, help="Require unique reagent category match when auto-detecting.")
parser.add_argument("sequences", type=str, nargs='+', help="One or more sequences to search for.")
args = parser.parse_args()

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

reagents = indexes.get_all_reagent_types() 
index_analyte = [(sequence.upper().strip(), "Query_{}".format(i)) for i, sequence in enumerate(args.sequences, start=1)]
if args.category:
    result = indexes.get_reagents_for_category(reagents, index_analyte, args.category)
else:
    category, result = indexes.get_reagents_auto_category(reagents, index_analyte, allow_multi_match=not args.unique_match)
    print("Category auto-detected: {}.".format(category))

# Output
for i, reagent_name in enumerate(result, start=1):
    print("Query_{}: {}".format(i, reagent_name))




