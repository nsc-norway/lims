import sys
import re
from genologics.lims import *
from genologics import config
from collections import defaultdict

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    i_os = [(i['uri'], o['uri']) for i, o in process.input_output_maps if o['output-generation-type'] == 'PerInput']
    lims.get_batch([o for i, o in i_os])

    repeated = set([i for i,o in i_os if o.udf.get('Repeat qPCR')])

    if repeated:
        requeue_at = defaultdict(list)
        step = Step(lims, id=process_id)
        stepconf = step.configuration
        for i in lims.get_batch(repeated):
            for stage in i.workflow_stages:
                if stage.step == stepconf:
                    index = stage.workflow.stages.index(stage)
                    requeue_at[stage.workflow.stages[index-1]].append(i)
                    break

        for stage, artifacts in requeue_at.items():
            lims.route_analytes(stage, artifacts)

if __name__ == "__main__":
    main(sys.argv[1])

