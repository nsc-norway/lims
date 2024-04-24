from genologics.lims import *
from genologics import config
import sys

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
process = Process(lims, id=sys.argv[1])

outputs = [o for o in process.all_outputs(resolve=True, unique=True) if o.type=='Analyte']

# Ensure that there is only one output container
if len(set(o.location[0] for o in outputs)) > 1:
    print("ERROR: Only one library tube strip is allowed")
    sys.exit(1)


# Ensure that the output container name was changed
if outputs[0].location[0].id == outputs[0].location[0].name:
    print("The container name should be changed to the barcode of the Library Tube Strip.")
    sys.exit(1)

# Fix output container name strip tube barcode, change "+" to "-" (BC reader keyboard layout)
outputs[0].location[0].name = outputs[0].location[0].name.replace("+", "-")
outputs[0].location[0].put()

