# Rename the output containers to indicate that a real container ID  should not be entered
# by the user
import sys
import datetime
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    containers = step.placements.selected_containers
    for c in containers:
        c.name = "DUMMY-{0:%y%m%d}-{1}".format(datetime.date.today(), c.id.split("-")[-1])
        c.put()

if __name__ == "__main__":
    main(sys.argv[1])

