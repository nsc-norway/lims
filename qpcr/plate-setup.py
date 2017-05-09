import sys
from genologics.lims import *
from genologics import config


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    i_os = project.input_output_maps
    inputs = process.all_inputs(unique=True, resolve=True)
    ###TODO  delete inputs = [i['uri'] for i,o in i_os]

    controls = ... 

    other_processes = lims.get_processes(inputartifactlimsid=next(iter(inputs)))
    for place_process in reversed(sorted(other_processes, key=lambda p: p.id)):
        if place_process.type_name.startswith("qPCR Plate Setup") and\
                set(place_process.all_inputs()) == set(inputs) - set(controls):
            break
    else:
        print "Sample placement process was not found for these inputs, ",
        print "make sure all inputs are selected."
        sys.exit(1)

    input_index = {
            (i, o['well'])
            for i,o in other_process.input_output_maps
            }

    current_96well_index = 0
    output_container = lims.create_container('384 well plate')
    placements = []
    input_replicate_id = {}
    for project in projects:
        proj_i_os = ((i, o) for (i, o) in i_os if i['uri'].samples[0].project == project)
        project_index_outputs = []
        for i, o in proj_i_os:
            container, well = i['uri'].location
            try:
                sample_id_sortable = int(i['uri'].name.partition("-")[0])
            except ValueError:
                sample_id_sortable = i['uri'].name
            project_index_outputs.append((sample_id_sortable, o['uri']))
        # List of positions, then 
        for index, output in sorted(project_index_outputs):
            out_row = "ABCDEFGHIJKLMNOP"
            replicate_id = input_replicate_id.get(input, 0)
            drow = replicate_id // 2
            dcol = replicate_id % 2
            input_replicate_id[input] = replicate_id + 1
            out_pos = "{0}:{1}".format(out_row[(current_96well_index*2) % 16 + drow], ((current_96well_index*2)//16) + 1 + dcol)
            placements.append((output, (output_container, out_pos)))
            current_96well_index += 1

    step = Step(lims, process_id)
    step.placements.set_placement_list(placements)
    step.placements.put()

main(sys.argv[1])

