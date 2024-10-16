import sys
from genologics import config
from genologics.lims import *

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

samplesheet_process = Process(lims, id=sys.argv[1])
bcl_convert_id = samplesheet_process.udf.get('BCL Convert LIMS-ID')
if bcl_convert_id:
    try:
        bcl_convert_process = Process(lims, id=bcl_convert_id)
        bcl_convert_process.get()
    except:
        pass
    if bcl_convert_process.udf.get('Status') in ["COMPLETED", "FAILED"]:
        step = Step(lims, id=bcl_convert_id)
        try:
            if step.current_state.upper() == "RECORD DETAILS":
                for na in step.actions.next_actions:
                    na['action'] = 'complete'
                step.actions.put()
            while step.current_state.upper() != "COMPLETED":
                step.advance()
                step.get(force=True)
        except:
            pass


