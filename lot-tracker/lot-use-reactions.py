import sys
import re
from genologics.lims import *
from genologics import config

# NOTE! This script needs to be run with Python 3 in order to correctly
# match nbsp characters in the regex.

def main(process_id):
    """Script to register lot usage and disable expired lots."""

    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    step = Step(lims, id=process_id)
    
    # Get the name of the kit type (same as in the "show lots")
    lots = step.reagentlots.reagent_lots
    kit_names = set(lot.reagent_kit_name for lot in lots)
    if len(kit_names) != 1:
        print("This script only supports steps with exactly one configured kit type")
        sys.exit(1)
    kit_name = next(iter(kit_names))
    # Get the total number of reactions in each box of this kit type (copied from "show lots" script)
    rxn_match = re.search(r"\b(\d+)rxn\b", kit_name)
    if not rxn_match:
        print("The kit name does not include the number of reactions (Nrxn).")
        sys.exit(1)
    kit_type_num_reactions = int(rxn_match.group(1))

    try:
        lots_used = process.udf['Lots used']
    except KeyError:
        print("Missing 'Lots used' field, this is a configuration error.")
        sys.exit(1)
    if not lots_used:
        print("Enter some text for 'Lots used'. If not tracking lots, enter 'None'.")
        sys.exit(1)
    match_string = r"Name:\s*([^,]+),\s*Lot#:\s*([^,]+),\s*Reactions:\s*(\d+),\s*Use:\s*(\d+)"
    lots_to_put = []
    for line in process.udf['Lots used'].splitlines():
        match = re.match(match_string, line)
        if match:
            name, lotnum, remaining, used = match.groups()
            lots = lims.get_reagent_lots(name=name, number=lotnum, kitname=kit_name)
            if len(lots) == 0:
                print("Lot number", lotnum, ", lot name", name, "not found.")
                sys.exit(1)
            elif len(lots) > 1:
                print("Lot number", lotnum, ", lot name", name, "matches multiple lots, which should not be possible.")
                sys.exit(1)
            lot = lots[0]
            before_remaining_reactions = None
            # Get reactions from the lot notes again (to limit race conditions if multiple steps are open)
            if lot.notes:
                reactions_match = re.match(r"\d+", lot.notes)
                if reactions_match:
                    before_remaining_reactions = int(reactions_match.group(0))
            # If there is nothing to be found in notes, we'll use the default number. Temporarily set the previous number
            # of remaining reactions, we'll update it soon
            if not before_remaining_reactions:
                before_remaining_reactions = kit_type_num_reactions
                prev_notes_text = lot.notes
                lot.notes = "{0} reactions remaining.".format(before_remaining_reactions)
                if prev_notes_text:
                    lot.notes += " " + prev_notes_text

            new_remaining_reactions = before_remaining_reactions - int(used)
            lot.notes = re.sub(r"\d+", str(new_remaining_reactions), lot.notes)
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
