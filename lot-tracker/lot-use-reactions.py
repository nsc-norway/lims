import sys
import re
from collections import defaultdict
from genologics.lims import *
from genologics import config



def get_remaining_reactions(lot):
    rm = re.search(r"-(\d+)R$", lot.name)
    if rm:
        return int(rm.group(1))
    else:
        raise ValueError("Unknown number of reactions for lot {0} / {1}.".format(lot.name, lot.lot_number))


def update_remaining_reactions(lot, new_reactions):
    if new_reactions > 0:
        lot.name = re.sub(r"-\d+R$", "-{0:02d}R".format(new_reactions), lot.name)
    elif new_reactions == 0:
        lot.name = re.sub(r"-\d+R$", "", lot.name)
        lot.status = "ARCHIVED"


def subtract_reactions(lot, num_reactions):
    current = get_remaining_reactions(lot)
    remain = current - num_reactions
    if remain >= 0:
        update_remaining_reactions(lot, remain)
    else:
        raise RuntimeError("Attempted to use {0} reactions from lot {1} / {2}, but there are "
                "only {3} reactions left.".format(
            num_reactions, lot.name, lot.lot_number, current
            ))


def parse_used_lots(used_lots_string):
    """Returns a dict kit_name => [(lot_name, lot_number, reactions), ...]."""
    kit = None
    result = defaultdict(list)
    for line in used_lots_string.splitlines():
        m1 = re.match(r"-- Kit: (.*) --", line)
        if m1:
            kit = m1.group(1)
        elif kit:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 4:
                m2 = re.match(r"use: (\d+)$", parts[3])
                if m2:
                    result[kit].append((parts[0], parts[1], int(m2.group(1))) )
    return result


def main(process_id):
    """Script to register lot usage and disable expired lots."""

    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    step = Step(lims, id=process_id)

    num_reactions_to_use = len(process.all_inputs(unique=True))
    
    all_lots = step.reagentlots.reagent_lots
    kits_lots = defaultdict(list)
    for lot in all_lots:
        kits_lots[lot.reagent_kit].append(lot)

    lot_usage_text = process.udf.get('Lots used')
    if lot_usage_text:
        # Parse the text and update lot reactions as specified
        used_lot_dict = parse_used_lots(lot_usage_text)
        if set(used_lot_dict.keys()) != set(kit.name for kit in kits_lots.keys()):
            print("The kits in the Lots used box do not match the kits in the Reagent Lot Tracking screeen")
            sys.exit(1)
        for field_kit, field_lots in used_lot_dict.items():
            try:
                kit_lots = next(lots for kit, lots in kits_lots.items() if kit.name == field_kit)
            except StopIteration:
                print("Kit {0} appears in Lots used, but is not configured for this step.")
                sys.exit(1)
            
            for (lot_name, lot_number, use_reactions) in field_lots:
                name_less_suffix = re.sub(r"\dR$", "", lot_name)
                try:
                    step_lot = next(lot for lot in kit_lots if 
                            lot.name.startswith(name_less_suffix) and
                            lot.lot_number == lot_number)
                except StopIteration:
                    print("Lot {0} / {1} specified in the Lots used field is not selected under Reagent "
                            "Lot Tracking at the top of the page.".format(lot_name, lot_number))
                    sys.exit(1)
                subtract_reactions(step_lot, use_reactions)
                kit_lots.remove(step_lot)

            if kit_lots:
                print("Found {0} lots in Reagent Lot Tracking section which does not appear in the Lots used box"
                        " for kit {1}.".format(len(kit_lots), field_kit))
                sys.exit(1)

    else:
        # For a single lot per kit, use the specified number of reactions. Otherwise, show an error.
        if all(len(lots) == 1 for lots in kits_lots.values()):
            for lot in all_lots:
                subtract_reactions(lot, num_reactions_to_use)
        else:
            print("Multiple lots used. Use the 'Show remaining rections' button to specify "
                   "how many reactions to use from each lot.")
            sys.exit(1)


    for lot in all_lots: # commit if no error
        lot.put()


if __name__ == "__main__":
    main(process_id=sys.argv[1])
