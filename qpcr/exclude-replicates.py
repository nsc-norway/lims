import sys
from genologics.lims import *
from genologics import config
from collections import defaultdict

# Exclude replicates with too large distance from the median, and set QC flags to FAILED 
# if two replicates fail for a sample

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)

    exclusion_threshold = process.udf['Replicate exclusion threshold']

    outputs_per_input = defaultdict(list)
    for i,o in process.input_output_maps:
        if o['output-generation-type'] == 'PerInput':
            outputs_per_input[i['limsid']].append(o['uri'])

    if not all(len(ops) == 3 for ops in outputs_per_input.values()):
        print("Number of replicates is not equal to 3. Check the protocol step configuration.")
        sys.exit(1)
    
    all_triplicate_outputs = sum((replicates for replicates in outputs_per_input.values()), [])
    lims.get_batch(all_triplicate_outputs)
    
    for replicates in outputs_per_input.values():
        qc_fail = False
        if not all('Raw CP' in rep.udf for rep in replicates):
            for rep in replicates:
                if rep.control_type and rep.name.startswith("No Template Control ") and rep.udf.get('Raw CP', 0) == 0:
                    # Special handling of NTC control. We should report a CP of 30 if the imported data value is
                    # zero or missing. It is not an error if this has a missing value - that's the desired outcome.
                    rep.udf['Raw CP'] = 30
                else:
                    rep.udf['Exclude'] = True
                    qc_fail = True
        else:
            raw_cps = sorted(rep.udf['Raw CP'] for rep in replicates)
            mid = len(raw_cps) // 2
            median_raw_cp = (raw_cps[mid] + raw_cps[~mid]) / 2
            num_excluded = 0
            for rep in replicates:
                if abs(rep.udf['Raw CP'] - median_raw_cp) > exclusion_threshold:
                    rep.udf['Exclude'] = True
                    num_excluded += 1
            if num_excluded == 2:
                qc_fail = True
        for rep in replicates:
            rep.qc_flag = "FAILED" if qc_fail else "PASSED"

    lims.put_batch(all_triplicate_outputs)


main(sys.argv[1])

