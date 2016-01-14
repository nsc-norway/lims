# Script to rename / modify reagent types.
# Special-purpose script which only handles a specific rename operation, 
# but can be adapted later.

import re
from genologics.lims import *
from genologics import config

def main():
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

    table = [l.split() for l in open('nextera_name_index.txt').readlines()]
    db = dict(("%s (%s)" % (t[1], t[2]), t) for t in table)

    updated = []
    for reg in lims.get_reagent_types():
        old_name = reg.name
        row = db.get(old_name)
        if row:
            new_name = "%s %s (%s)" % tuple(row)
            reg.name = new_name
            updated.append(reg)
            del db[old_name]

    if len(updated) == 96:
        for reg in updated:
            print "Updating ", reg.name
            return
            reg.put()
    else:
        print "Found unexpected number of indexes:", len(updated)
        print "Missing:"
        for x in db.keys():
            print x

main()

