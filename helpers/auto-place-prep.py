import sys
from genologics.lims import *
from genologics import config

def parse_sample_name(name):
    try:
        number, _, text = name.partition("-")
        return (int(number), text)
    except ValueError:
        return (name,)

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    step = Step(lims, id=process_id)
    step.placements.get()
    inputs = process.all_inputs(unique=True, resolve=True)
    lims.get_batch(i.samples[0] for i in inputs)

    # One output container is created by default. This will iterate over
    # that one container.
    output_containers_iter = iter(step.placements.selected_containers)

    input_list = []
    for ii,oo in process.input_output_maps:
        if oo['output-generation-type'] == "PerInput":
            i = ii['uri']
            input_list.append((
                i.samples[0].project.name,
                parse_sample_name(i.name),
                oo['uri']))

    placements = []

    outwell_index = 999 # Make it request new container on first sample.
    for _, _, o in sorted(input_list):
        outwell_index += 1
        if outwell_index >= 96:
            try:
                output_container = next(output_containers_iter)
            except StopIteration:
                output_container = lims.create_container('96 well plate')
            outwell_index = 0
        outwell = "{}:{}".format(
                "ABCDEFGH"[outwell_index % 8],
                1 + outwell_index // 8
                )
        placements.append((o.stateless, (output_container, outwell)))
    step.placements.set_placement_list(placements)
    step.placements.post()

main(sys.argv[1])

