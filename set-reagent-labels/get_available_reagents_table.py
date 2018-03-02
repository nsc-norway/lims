# Script to list all the indexes with category, name, sequence. Can be used to cache a list
# of reagents.

import re
from genologics.lims import *
from genologics import config

def main():
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

    reagent_types = lims.get_reagent_types()
    for reg in reagent_types:
        print reg.category + "\t" + reg.name + "\t" + reg.sequence


main()

