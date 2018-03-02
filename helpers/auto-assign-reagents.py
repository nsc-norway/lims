import sys
import os
from itertools import cycle
from genologics.lims import *
from genologics import config

def parse_sample_name(name):
    try:
        number, _, text = name.partition("-")
        return (int(number), text)
    except ValueError:
        return (name,)

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    step = Step(lims, id=process_id)
    outputs = process.all_outputs(unique=True, resolve=True)

    reagent_category = step.reagents.reagent_category
    with open(os.path.join(
        os.path.dirname(__file__),
        "ouslims_indexes.txt"
        )) as index_file:
        reagents = sorted( name for 
            name, category, sequence
            in (line.split("\t") for line in index_file)
            if category == reagent_category)
    sorted_outputs = sorted( (o.location[0].id, o.location[1], o)
            for o in outputs
            if o.type == 'Analyte')
    for index, (_, _, output) in zip( cycle(reagents), sorted_outputs ):
        print "Loule"
        step.reagents.output_reagents[output] = index
    step.reagents.post()

main(sys.argv[1])

