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
    kit_names = set(lot.reagent_kit_name for lot in lots)
    if len(kit_names) != 1:
        print("This script only supports steps with exactly one configured kit type")
        sys.exit(1)
    kit_name = next(iter(kit_names))

    # Get the total number of reactions in each box of this kit type
    rxn_match = re.search(r"\b(\d+)rxn\b", kit_name)
    if not rxn_match:
        print("The kit name does not include the number of reactions (Nrxn).")
        sys.exit(1)
    kit_type_num_reactions = int(rxn_match.group(1))

    # Constructing one line for each lot, with textual information
    lot_data_lines = []
    for lot in lots:
        # For new lots, we only have this information
        lot_remaining_reactions = kit_type_num_reactions
        # Try to get remaining reactions from notes
        if lot.notes:
            reactions_match = re.match(r"\d+", lot.notes)
            if reactions_match:
                lot_remaining_reactions = int(reactions_match.group(0))

        use_reactions = min(lot_remaining_reactions, reactions_needed)
        reactions_needed -= use_reactions
        output_text = "Name: {0}, Lot#: {1}, Remaining: {2}, Use: {3}".format(
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
