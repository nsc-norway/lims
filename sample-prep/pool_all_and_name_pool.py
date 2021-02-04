import sys
from genologics.lims import *
from genologics import config
import requests

def main(process_id, name_mode, pool_suffix=""):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    poolable = step.pools.available_inputs
    if name_mode == "project":
        pool_name = poolable[0].samples[0].project.name + pool_suffix
    elif name_mode == "project_part":
        parts = poolable[0].samples[0].project.name.split("-")
        if len(parts) >= 3:
            mid_part = "-".join(parts[1:3])
        else:
            mid_part = poolable[0].samples[0].project.name
        pool_name = mid_part + pool_suffix
    elif name_mode == "run":
        try:
            with open("/var/lims-scripts/covid-run-count.txt") as f:
                count = int(f.read().strip())
        except IOError:
            count = 0
        count += 1
        pool_name = "Run{:03d}{}".format(count, pool_suffix)
    else:
        pool_name = "Pool"
    try:
        step.pools.create_pool(pool_name, poolable)
    except requests.exceptions.HTTPError as e:
        if 'artifacts with the same reagent labels' in str(e):
            print("Duplicate indexes detected. Cannot pool these inputs.")
            sys.exit(1)
        else:
            raise e
    if name_mode == "run": # Write new count here, in case of no error
        open("/var/lims-scripts/covid-run-count.txt", "w").write(str(count))

if __name__ == "__main__":
    main(*sys.argv[1:])
