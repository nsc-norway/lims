import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id, archivable_kit_names_re):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    step = Step(lims, id=process_id)
    if step.reagentlots:
        for lot in step.reagentlots.reagent_lots:
            if any(re.match(kit_re, lot.reagent_kit_name) for kit_re in archivable_kit_names_re):
                if not "dummy" in lot.lot_number.lower():
                    lot.status = "ARCHIVED"
                    lot.put()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
