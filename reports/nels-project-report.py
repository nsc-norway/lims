from genologics.lims import *
from genologics import config
import datetime

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

date_str = str(datetime.date.today() - datetime.timedelta(days=-1))
timestamp_str = date_str + "T00:00:00Z"
nels_projects = []

for pe in lims.get_processes(type="Project Evaluation Step", last_modified=timestamp_str):
    project = pe.all_inputs()[0].samples[0].project
    if project.udf.get('Delivery method') == "NeLS project":
        nels_projects.append((project.name, project.udf.get('NeLS project identifier', '--not provided--')))

if nels_projects:
    print("*** New NeLS projects registered since {0} ***".format(date_str))
    print("Project name\t\tNeLS ID")
    for project in nels_projects:
        print("{0}\t\t{1}".format(*project))

