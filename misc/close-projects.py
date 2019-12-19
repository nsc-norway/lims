from genologics.lims import *
from genologics import config
import datetime

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

projects = lims.get_projects(open_date="2019-05-01")

for project in projects:
    if not project.close_date and project.name.lower().startswith("diag-"):
        if project.open_date < "2019-11-01":
            print project.name
            project.close_date = str(datetime.date.today())
            project.put()
