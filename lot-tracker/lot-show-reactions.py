import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id):
    """Show the remaining reactions in the selected lots. This works with steps which have only one kit
    type configured.
    """
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    step = Step(lims, id=process_id)
    process = Process(lims, id=process_id)
    reactions_needed = len(process.all_inputs(unique=True))
    if not step.reagentlots:
        sys.exit(0)

    # Get the name of the kit type
    lots = step.reagentlots.reagent_lots

    # Constructing one line for each lot, with textual information
    lot_data_lines = []
    for lot in lots:
        # For new lots, we only have this information
        lot_remaining_reactions = None

        # Try to get remaining reactions from notes
        if lot.notes:
            reactions_match = re.match(r"\d+", lot.notes)
            if reactions_match:
                lot_remaining_reactions = int(reactions_match.group(0))

        # Get the total number of reactions in box from lot name
        if lot_remaining_reactions is None:
            r_match = re.search(r"\b(\d+)R\b", lot.name)
            if not r_match:
                print("The lot name", lot.name, "does not include the number of reactions (nR).")
                sys.exit(1)
            lot_remaining_reactions = int(r_match.group(1))

        use_reactions = min(lot_remaining_reactions, reactions_needed)
        reactions_needed -= use_reactions
        output_text = "Name: {0}, Lot#: {1}, Reactions: {2}, Use: {3}".format(
                        lot.name,
                        lot.lot_number,
                        lot_remaining_reactions,
                        use_reactions
                        )
        if use_reactions == 0:
            output_text += ", Lot not used"
        lot_data_lines.append(output_text)

    process.udf['Lots used'] = "\n".join(lot_data_lines)
    process.put()


if __name__ == "__main__":
    main(process_id=sys.argv[1])


