import sys
from genologics.lims import *
from genologics import config

# Take average of UDF in pool inputs and assign to pool

def main(process_id, fields):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    step = Step(lims, id=process_id)

    lims.get_batch(process.all_inputs(unique=True) + process.all_outputs(unique=True))
    
    outputs = []

    for pool in step.pools.pooled_inputs:
        for i, field in enumerate(fields):
            value = 0.0
            try:
                for input in pool.inputs:
                        value += input.udf[field]
                pool.output.udf[field] = value / len(pool.inputs)
                outputs.append(pool.output)
            except KeyError:
                pass # In case we don't have this field, continue to next field
                     # (this is not the right place to report an error)
    lims.put_batch(outputs)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])

