import sys
import re
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
        projects = set(sample.project.name for inp in poolable for sample in inp.samples)
        project_pool_names = []
        s_bit = set()
        for project in projects:
            # The following regexs are the same as the ones used to check names, in
            # covid_project_pre_checks_and_setup.py
            m = re.match(r"\d+-([NS]\d)-([^-]+).*", project)
            m_new_fhi_name = re.match(r"(FHI\d+)-(S\d)-([^-]+).*", project)
            if m:
                project_pool_names.append(m.group(2))
                s_bit.add(m.group(1))
            elif m_new_fhi_name:
                project_pool_names.append(m_new_fhi_name.group(1))
                s_bit.add(m_new_fhi_name.group(2))
            else:
                project_pool_names.append("ERROR")
                s_bit.add("?")
        pool_name = "x".join(s_bit) + "-" + "_".join(project_pool_names) + pool_suffix
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
