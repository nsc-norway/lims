# Script to rename / modify reagent types.
# Special-purpose script which only handles a specific rename operation, 
# but can be adapted later.

from genologics.lims import *
from genologics import config

def main():
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    lims.get_reagent_types()

    cells = open("xt.txt").read().split()
    name_sequence = [
            (col, sequence)
            for col, sequence
            in zip(cells[::2], cells[1::2])
            ]

    updated = []
    print name_sequence



main()

