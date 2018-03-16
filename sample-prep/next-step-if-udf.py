import sys
from genologics import config
from genologics.lims import *

def main(process_id, udf_name, set_step_udf_value, step_name):
    """Sets next step based on a configurable Sample-level UDF.

    This works similarly to the diag-step-select.py, but only does one of the branches,
    leaves the other at the default value.
    """
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    
    next_step_uri = None

    # Get next steps
    for transition in step.configuration.transitions:
        if transition.get('name') == step_name:
            next_step_uri = transition['next-step-uri']

    if not next_step_uri:
        print "Couldn't find the configured steps"
        sys.exit(1)

    next_actions = step.actions.next_actions
    # Pre-cache everything
    artifacts = [Artifact(lims, uri=na['artifact-uri']) for na in next_actions]
    lims.get_batch(artifacts)
    lims.get_batch(artifact.samples[0] for artifact in artifacts)

    # For error reporting
    missing_values = []

    for na, artifact in zip(next_actions, artifacts):
        try:
            udf_value = artifact.samples[0].udf[udf_name]
        except KeyError:
            missing_values.append(artifact.name)
            continue
        
        if str(udf_value) == set_step_udf_value:
            na['action'] = 'nextstep'
            na['step-uri'] = next_step_uri

    if missing_values:
        print "{0} not specified for samples: {1}".format(udf_name, ", ".join(missing_values))
        sys.exit(1)

    step.actions.put()


main(*sys.argv[1:])

