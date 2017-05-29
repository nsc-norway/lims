import sys
import re
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    i_os = [(i['uri'].stateless, o['uri'].stateless)
            for i, o in process.input_output_maps if o['output-generation-type'] == 'PerInput']
    lims.get_batch([o for i, o in i_os] + [i for i,o in i_os])

    step = Step(lims, id=process_id)
    default_next_step_uri = step.configuration.transitions[0]['next-step-uri']
    
    for action in step.actions.next_actions:
        input = Artifact(lims, uri=action['artifact-uri'])
        repeat = any(o.stateless.qc_flag == "FAILED" for i, o in i_os if i == input)
        if input.control_type:
            action['action'] = "remove"
        elif repeat:
            for stage in input.workflow_stages:
                if stage.step == step.configuration:
                    stage_index = stage.workflow.stages.index(stage)
                    rework_step = stage.workflow.stages[stage_index - 1].step
                    break
            action['action'] = "rework"
            #action['step-uri'] = default_next_step_uri
            action['rework-step-uri'] = rework_step.uri
        else:
            action['action'] = "nextstep"
            action['step-uri'] = default_next_step_uri

    step.actions.put()

if __name__ == "__main__":
    main(sys.argv[1])

