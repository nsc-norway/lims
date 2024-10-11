import sys
import re
from genologics import config
from genologics.lims import *

# Script to fill the 'next action' field with the first next step 
# matching the specified regular expression

def main(process_id, name_pattern):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    if step.configuration.transitions:
        for tn in step.configuration.transitions:
            if re.match(name_pattern, tn['name']):
                next_step_uri = tn.get("next-step-uri")
                action = "nextstep"
                break
        else:
            print(f"ERROR: Cannot find next step matching pattern '{name_pattern}'")
            sys.exit(1)
    else:
        action = "complete"

    for next_action in step.actions.next_actions:
        if next_action.get('action') != "remove": # Don't set next action for controls, which have default "remove"
            if action == "nextstep":
                next_action['step-uri'] = next_step_uri
            next_action['action'] = action
    step.actions.put()

main(
        process_id=sys.argv[1],
        name_pattern=sys.argv[2]
        )
