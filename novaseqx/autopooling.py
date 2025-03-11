from genologics.lims import *
from genologics import config
import sys

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} PROCESS_ID")
    sys.exit(1)

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

process = Process(lims, id=sys.argv[1])
step = Step(lims, id=sys.argv[1])

poolable = step.pools.available_inputs
main_inputs = [p for p in poolable if not p.udf.get('Spike-in %')]
for main_input in main_inputs:
    step.pools.create_pool(main_input.name, [main_input])

