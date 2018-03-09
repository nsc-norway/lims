# Changes the "technician" field of recently run processes which have "escalation"
# The technician is set to API user, so the original user can complete the review
# if required
from genologics.lims import *
from genologics import config
from datetime import datetime, timedelta
import sys
#import logging
#logging.basicConfig()
#logging.getLogger().propagate =True
#logging.getLogger().setLevel(logging.DEBUG)

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

try:
    lims.check_version()
except:
    sys.exit(0) # Since this will run as a cron job, we just die silently if LIMS is unreachable

two_hours_ago = (datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
processes = lims.get_processes(last_modified=two_hours_ago)
takeover_user = Researcher(lims, id="3")
for process in processes:
    step = Step(lims, id=process.id)
    if step.current_state == "Under Review":
        if process.technician != takeover_user:
            process.technician = takeover_user
            process.put()

