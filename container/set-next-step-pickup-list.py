import sys
from genologics.lims import *
from genologics import config

# If input is on 96 well plate, to next step; otherwise, jump to next next step

NEXT_ACTION = "nextstep"


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    assert len(step.configuration.transitions) >= 2, "Error: At least two \"Next step\" should be configured."
    tn = step.configuration.transitions[0]
    tjump1 = step.configuration.transitions[1]
    default_next_step_uri = tn['next-step-uri']
    jump1_step_uri = tjump1['next-step-uri']

    for action in step.actions.next_actions:
        artifact_uri = action['artifact-uri']
        action.clear()
        action['artifact-uri'] = artifact_uri
        input = Artifact(lims, uri=action['artifact-uri'])
        if input.location[0].type_name == "96 well plate":
            action['step-uri'] = default_next_step_uri
        else:
            action['step-uri'] = jump1_step_uri

        action['action'] = NEXT_ACTION

    step.actions.put()


if __name__ == "__main__":
    main(sys.argv[1])
