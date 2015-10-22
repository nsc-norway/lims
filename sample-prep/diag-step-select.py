import sys
from genologics import config
from genologics.lims import *

def main(process_id, high_conc_step, low_conc_step=None):
    """Sets next step based on normalized conc., to support high/low 
    concentration samples in one protocol.

    use: 
    diag-step-select.py process_id high_conc_step low_conc_step
    
    Specify steps on command line, if using only one step parameter
    then all samples will be directed to that step.
    """
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    
    high_conc_step_uri = low_conc_step_uri = None

    if not low_conc_step:
        low_conc_step = high_conc_step

    # Get next steps
    for transition in step.configuration.transitions:
        if transition.get('name') == high_conc_step:
            high_conc_step_uri = transition['next-step-uri']
        if transition.get('name') == low_conc_step:
            low_conc_step_uri = transition['next-step-uri']

    if not high_conc_step_uri or not low_conc_step_uri:
        print "Couldn't find the configured steps"
        sys.exit(1)

    next_actions = step.actions.next_actions
    # Pre-cache everything
    artifacts = lims.get_batch(Artifact(lims, uri=na['artifact-uri']) for na in next_actions)
    samples = lims.get_batch(artifact.samples[0] for artifact in artifacts)

    # For error reporting
    missing_values = []

    for na, artifact in zip(next_actions, artifacts):
        try:
            conc_udf = artifact.samples[0].udf['Normalized amount of DNA (ng) Diag']
        except KeyError:
            missing_values.append(artifact.name)
            continue
        
        if conc_udf == 200:
            na['action'] = 'nextstep'
            na['step-uri'] = low_conc_step_uri
        elif conc_udf == 3000:
            na['action'] = 'nextstep'
            na['step-uri'] = high_conc_step_uri
        else:
            print "Invalid value", conc_udf, "for sample", artifact.name
            sys.exit(1)

    if missing_values:
        print "Normalized concentration not specified for samples: ", ", ".join(missing_values)
        sys.exit(1)

    step.actions.put()


main(*sys.argv[1:])

