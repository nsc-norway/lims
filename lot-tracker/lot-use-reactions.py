import sys
from genologics.lims import *
from genologics import config

def main(process_id):
    """AAA"""
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    step = Step(lims, id=process_id)
    if step.reagentlots:
        for lot in step.reagentlots.reagent_lots:
            pass


if __name__ == "__main__":
    main(*sys.argv)
