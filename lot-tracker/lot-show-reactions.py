import sys
import re
from genologics.lims import *
from genologics import config

def get_suggested_reactions_used_per_lot(kit_lots, num_samples):
    exp_remain_lot = sorted((lot.expiry_date, get_remaining_reactions(lot), lot) for lot in this_kit_lots)
    num_reactions_left_to_use = num_reactions_to_use
    lot_used = []
    for expiry, num_remain, lot in remain_lot:
        use_of_this_lot = min(num_reactions_left_to_use, num_remain)
        lot_used.append((lot, use_of_this_lot))
    return lot_used


def main(process_id):
    """Show the remaining reactions in the selected lots. This works with steps which have only one kit
    type configured.
    """
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    step = Step(lims, id=process_id)
    process = Process(lims, id=process_id)
    reactions_needed = len(process.all_inputs(unique=True))

    num_reactions_to_use = len(process.all_inputs(unique=True))

    all_lots = step.reagentlots.reagent_lots

    lots = step.reagentlots.reagent_lots
    kits_lots = defaultdict(list)
    lot_data_lines = []
    for lot in all_lots:
        kits_lots[lot.reagent_kit].append(lot)

    for kit, lots in kits_lots.items():
        lot_data_lines.append("-- Kit: {0} --".format(kit.name))
        for lot, usable in get_suggested_reactions_used_per_lot(lots, num_reactions_to_use):
            pass # TODO!

    process.udf['Lots used'] = "\n".join(lot_data_lines)
    process.put()


if __name__ == "__main__":
    main(process_id=sys.argv[1])


