import sys
from genologics.lims import *
from genologics import config

def main(process_id, name_mode, pool_suffix=""):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    poolable = step.pools.available_inputs
    if name_mode == "project":
        pool_name = poolable[0].samples[0].project.name + pool_suffix
    elif name_mode == "run":
        try:
            with open("/var/lims-scripts/covid-run-count.txt") as f:
                count = int(f.read().strip())
        except IOError:
            count = 0
        count += 1
        pool_name = "Run {}{}".format(count, pool_suffix)
        open("/var/lims-scripts/covid-run-count.txt", "w").write(str(count))
    else:
        pool_name = "Pool"
    step.pools.create_pool(pool_name, poolable)

if __name__ == "__main__":
    main(*sys.argv[1:])