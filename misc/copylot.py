from genologics.lims import *
from genologics import config
import sys

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
attrs = ["name", "lot_number", "created_date", "last_modified_date", "expiry_date", "created_by", "last_modified_by", "status", "notes"]

if len(sys.argv) <= 3:
    print("usage: copylot.py FROM_LOT TO_LOT LOTNAME")
    sys.exit(1)

def copy_lot(old_lot, new_kit):
    new_lot_data = {}
    for attr in attrs: 
        new_lot_data[attr] = getattr(old_lot, attr)
    new_lot_data['reagent_kit'] = new_kit
    ReagentLot.create(lims, **new_lot_data)

#old_kit = lims.get_reagent_kits(name="Diag_HiSeq 2500 Cluster Kit 1/2")[0]
new_kit = lims.get_reagent_kits(name=sys.argv[2])[0]
all_lots = lims.get_reagent_lots(kitname=sys.argv[1])

for lot in all_lots:
    if any(lot.name.startswith(a) for a in sys.argv[3:]):
        print("> Found lot")
        for attr in attrs:
            print("%20s: %s" % (attr, getattr(lot, attr)))
        y = raw_input(">Enter y to copy this lot: ")
        if y == "y":
            copy_lot(lot, new_kit)
            a = raw_input(">Copied. Archive it: ")
            if a == "y":
                lot.status="ARCHIVED"
                lot.put()
        else:
            break

