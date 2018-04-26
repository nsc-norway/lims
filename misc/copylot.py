from genologics.lims import *
from genologics import config
import sys

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

def copy_lot(old_lot, new_kit):
    new_lot_data = {}
    for attr in ["name", "lot_number", "created_date", "last_modified_date", "expiry_date", "created_by", "last_modified_by", "status", "notes"]:
        new_lot_data[attr] = getattr(old_lot, attr)
    new_lot_data['reagent_kit'] = new_kit
    ReagentLot.create(lims, **new_lot_data)

#old_kit = lims.get_reagent_kits(name="Diag_HiSeq 2500 Cluster Kit 1/2")[0]
new_kit = lims.get_reagent_kits(name="NSC_MiSeq Reagent Kit 2/2")[0]
old_lots = lims.get_reagent_lots(kitname="Diag_MiSeq Reagent Kit 2/2")

copied = 0
for lot in old_lots:
    if lot.status =="ACTIVE" and lot.name.endswith("V3"):
        copy_lot(lot, new_kit)
        copied += 1

print "Copied", copied, "lots"



