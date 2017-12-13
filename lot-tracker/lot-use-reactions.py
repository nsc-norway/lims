import sys
import re
from collections import defaultdict
from genologics.lims import *
from genologics import config



def get_remaining_reactions(lot):
    rm = re.search(r"-\d+R$", lot.name)
    if rm:
        return int(rm.group(1))
    else:
        raise ValueError("Unknown number of reactions for lot {0} / {1}.".format(lot.name, lot.lot_number))

def update_remaining_reactions(lot, new_reactions):
    lot.name = re.sub(r"-\d+R$", str(new_reactions), lot.name)

def main(process_id, mode):
    """Script to register lot usage and disable expired lots."""

    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    step = Step(lims, id=process_id)

    num_reactions_to_use = len(process.all_inputs(unique=True))
    
    lots = step.reagentlots.reagent_lots
    kits_lots = defaultdict(list)
    for lot in lots:
        kits_lots[lot.reagent_kit].append(lot)

    for kit, this_kit_lots in kits_lots.items():
        lot_used = get_suggested_reactions_used_per_lot(this_kit_lots, num_reactions_to_use, False)



    match_string = r"Name:\s*([^,]+),\s*Lot#:\s*([^,]+),\s*Reactions:\s*(\d+),\s*Use:\s*(\d+)"
    lots_to_put = []
    for line in process.udf['Lots used'].splitlines():
        match = re.match(match_string, line)
        if match:
            name, lotnum, remaining, used = match.groups()
            lots = [lot for lot in lots if lot.name == name and lot.lot_number == lotnum]
            if len(lots) == 0:
                print("Lot number", lotnum, ", lot name", name, "not found.")
                sys.exit(1)
            elif len(lots) > 1:
                print("Lot number", lotnum, ", lot name", name, "matches multiple lots, which should not be possible.")
                sys.exit(1)
            lot = lots[0]

            # Get reactions from the lot notes again (to limit race conditions if multiple steps are open)
            before_remaining_reactions = None
            if lot.notes:
                reactions_match = re.match(r"\d+", lot.notes)
                if reactions_match:
                    before_remaining_reactions = int(reactions_match.group(0))
            if before_remaining_reactions is None:
                # If there is nothing to be found in notes, we'll use the default number. Temporarily set the previous number
                # of remaining reactions, we'll update it soon
                r_match = re.search(r"\b(\d+)R\b", name)
                if not r_match:
                    print("The lot name", name, "does not include the number of reactions (nR).")
                    sys.exit(1)
                before_remaining_reactions = int(r_match.group(1))
                prev_notes_text = lot.notes
                lot.notes = "{0} reactions remaining.".format(before_remaining_reactions)
                if prev_notes_text:
                    lot.notes += " " + prev_notes_text

            new_remaining_reactions = before_remaining_reactions - int(used)
            lot.notes = re.sub(r"^\d+", str(new_remaining_reactions), lot.notes)
            if new_remaining_reactions < 0:
                print("Error: Attempted to use", used, "reactions from lot", name, lotnum + ", but only", before_remaining_reactions, "available.")
                sys.exit(1)
            if new_remaining_reactions == 0:
                lot.state = "ARCHIVED"
            lots_to_put.append(lot)

    for lot in lots_to_put: # commit
        lot.put()


if __name__ == "__main__":
    main(process_id=sys.argv[1])
