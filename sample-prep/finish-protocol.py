import sys
import os
import time
import subprocess
from genologics import config
from genologics.lims import *

def main(process_id, is_subprocess = False):
    """Finishes the current step and the next one.

    Used in the Diag SureSelect workflow.

    For use with the "end of protocol" step which is not used for anything.
    """
    if not is_subprocess:
        DEVNULL = open(os.devnull, 'wb')
        subprocess.Popen(["/usr/bin/python"] + sys.argv + ['True'], stdout=DEVNULL, stdin=DEVNULL, stderr=DEVNULL)
    else:
        lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
        step = Step(lims, id=process_id)
        default_next = step.configuration.transitions[0]
        next_uri = default_next.get('next-step-uri')
        if all(na.get('step-uri') == next_uri for na in step.actions.next_actions):
            artifacts = [Artifact(lims, uri=na['artifact-uri']).stateless for na in step.actions.next_actions]
            next_step_cfg = ProtocolStep(lims, uri=next_uri)
            queue = next_step_cfg.queue()
            for attempt in xrange(5):
                if set(artifact.id for artifact in queue.artifacts) >= set(artifact.id for artifact in artifacts):
                    break
                else:
                    time.sleep(1)
                    queue.get(force=True)
            else:
                print "Can't find some of these artifacts in queue:",\
                                ", ".join(artifact.uri for artifact in artifacts)
                print "Queue:", ", ".join(artifact.uri for artifact in queue.artifacts)
                sys.exit(1)

            next_step = lims.create_step(next_step_cfg, artifacts)
            for na in next_step.actions.next_actions:
                na['action'] = 'complete'
            next_step.actions.put()
            while next_step.current_state.upper() != "COMPLETED":
                next_step.advance()

main(*sys.argv[1:])
