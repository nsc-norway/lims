from genologics.lims import *
from genologics import config
import datetime
import sys
import re

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

if len(sys.argv) > 1 and re.match(r"\d\d\d\d-\d\d-\d\d", sys.argv[1]):
    until_date = sys.argv[1]
else:
    until_date = raw_input("Enter until date (yyyy-mm-dd): ")


projects = lims.get_projects(open_date=until_date)

for project in projects:
    if not project.close_date and project.name.lower().startswith("diag-"):
        if project.open_date < until_date:
            print "Closing", project.name
            project.close_date = str(datetime.date.today())
            project.put()
