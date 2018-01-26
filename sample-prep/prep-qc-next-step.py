import sys
import re
from genologics.lims import *
from genologics import config

# This one's quite special.... If the artifact is marked as FAILED on this step, the next 
# step should be set to "rework from the start of the workflow". It assumes that there is
# one level of input/output between the current artifact and the one in the start of the 
# workflow. In the current usage, that's a fragmentation step. If QC is OK, it should just
# go to the next step.


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    i_os = [(i['uri'].stateless, o['uri'].stateless)
            for i, o in process.input_output_maps if o['output-generation-type'] == 'PerInput']
    lims.get_batch([o for i, o in i_os] + [i for i,o in i_os])

    step = Step(lims, id=process_id)
    assert len(step.configuration.transitions) == 1, "Error: Exactly one \"Next step\" should be configured."
    tn = step.configuration.transitions[0]
    default_next_step_uri = tn['next-step-uri']
    default_next_action = "nextstep"

    inputs= [i for i,o in i_os]

    for action in step.actions.next_actions:
        artifact_uri = action['artifact-uri']
        action.clear()
        action['artifact-uri'] = artifact_uri
        input = Artifact(lims, uri=action['artifact-uri'])
        repeat = any(o.stateless.qc_flag == "FAILED" for i, o in i_os if i == input)
        if repeat:
            action['action'] = "rework"
            parent_artifact = next(
                    i['uri']
                    for i, o in input.parent_process.input_output_maps
                    if o['uri'].id == input.id
                    )
            rework_step = parent_artifact.workflow_stages[-1].workflow.stages[0].step
            action['step-uri'] = rework_step.uri
            my_processes = lims.get_processes(inputartifactlimsid=parent_artifact.id,type=rework_step.name)
            print "yo", my_processes[-1].type_name
            action['rework-step-uri'] = my_processes[-1].uri.replace("/processes/", "/steps/")
        else:
            action['action'] = default_next_action
            action['step-uri'] = default_next_step_uri

    step.actions.put()

if __name__ == "__main__":
    main(sys.argv[1])

