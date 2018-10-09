from genologics.lims import *
from genologics import config
import datetime

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

date_str = str(datetime.date.today() - datetime.timedelta(days=-1))
timestamp_str = date_str + "T00:00:00Z"
nels_tsd_projects = []

for project in lims.get_projects(last_modified=timestamp_str):
    if project.udf.get('Delivery method') == "NeLS project":
        nels_tsd_projects.append((project.name, project.udf.get('NeLS project identifier', '--not provided--')))
    elif project.udf.get('Delivery method') == "TSD project":
        nels_tsd_projects.append((project.name, "TSD"))

if nels_tsd_projects:
    print("*** New NeLS/TSD projects registered since {0} ***".format(date_str))
    print("Project name\t\tNeLS ID")
    for project in nels_tsd_projects:
        print("{0}\t\t{1}".format(*project))

