import sys
from genologics.lims import *
from genologics import config
from collections import defaultdict
import re

alpha = "ABCDEFGHIJKLMNOP"

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD) 
    process = Process(lims, id=process_id)
    step = Step(lims, id=process_id)
    step.placements.get()
    inputs = process.all_inputs(unique=True, resolve=True)

    controls = [i for i in inputs if i.control_type]

    try:
        other_processes = lims.get_processes(inputartifactlimsid=next((i for i in inputs if not i.control_type)).id)
    except StopIteration:
        print "Error: Only controls found, no samples."
        sys.exit(1)

    for place_process in reversed(sorted(other_processes, key=lambda p: p.id)):
        if place_process.type_name.startswith("qPCR Plate Setup") and\
                set(place_process.all_inputs()) == set(inputs) - set(controls):
            break
    else:
        print "Sample placement process was not found for these inputs, ",
        print "make sure all inputs are selected."
        sys.exit(1)

    sample_inputs = place_process.all_inputs(unique=True)

    placements_96 = Step(lims, id=place_process.id).placements
    placement_list = placements_96.get_placement_list()
    # Assert require only one container, as we only want to deal with one output (384) here
    assert len(set(c for _, (c, w) in placement_list)) == 1, "Exactly one container must be used on placement step"

    assert len(placements_96.selected_containers) == 1,\
            "Exactly one container required for qPCR step."

    output_container = next(iter(step.placements.selected_containers))

    control_outputs = [o['uri'] for i, o in process.input_output_maps 
            if o['output-generation-type'] == 'PerInput' and i['uri'].control_type]

    if output_container.type_name == '96 well plate':
        placements = place_standards_96(output_container, control_outputs)
        pos = pos_96
        assert not any(int(w.split(":")[1]) > 3 for _, (c, w) in placement_list),\
                "You can only use the first 3 columns for 96 format qPCR."
    elif output_container.type_name == '384 well plate':
        placements = place_standards_384(output_container, control_outputs)
        pos = pos_384
    else:
        print "Unexpected output container type '" + str(output_container.type_name) + "'."

    outputs_per_input = defaultdict(list)
    sample_input_ids = set(i.id for i in sample_inputs)
    for ii,oo in process.input_output_maps:
        if oo['output-generation-type'] == "PerInput" and ii['limsid'] in sample_input_ids:
            outputs_per_input[ii['limsid']].append(oo['uri'])

    placement_output_input = dict((oo['limsid'], ii['limsid']) for ii, oo in place_process.input_output_maps)
    input_pos = dict((placement_output_input[output.id], w) for output, (c, w) in placement_list)
    for i in sample_inputs:
        row, col = input_pos[i.id].split(":")
        irow = alpha.index(row)
        icol = int(col)-1
        for i_rep, o in enumerate(sorted(outputs_per_input[i.id], key=lambda a: a.id)):
            outrow, outcol = pos(irow, icol, i_rep)
            outwell = "{0}:{1}".format(alpha[outrow], str(outcol+1))
            placements.append((o.stateless, (output_container, outwell)))
    step.placements.set_placement_list(placements)
    step.placements.post()

def place_standards_384(container, controls):
    placements = []
    control_replicate = {}
    for control in sorted(controls, key=lambda control: control.id):
        m = re.match(r"Standard (\d)", control.name)
        if m:
            repl = control_replicate.get(control.name, 0)
            control_replicate[control.name] = repl + 1
            std_index = int(m.group(1))-1
            row = alpha[(2*std_index)+1]
            col = 2 + repl*2
            placements.append((control.stateless, (container, "{0}:{1}".format(row, col))))
        elif control.name.startswith("No Template Control "):
            repl = control_replicate.get(control.name, 0)
            control_replicate[control.name] = repl + 1
            ntc_placements = ['B:8', 'D:8', 'F:8']
            placements.append((control.stateless, (container, ntc_placements[repl])))
    return placements


def place_standards_96(container, controls):
    placements = []
    control_replicate = {}
    for control in sorted(controls, key=lambda control: control.id):
        m = re.match(r"Standard (\d)", control.name)
        repl = control_replicate.get(control.name, 0)
        control_replicate[control.name] = repl + 1
        if m:
            placements.append((control.stateless, (container, "{0}:{1}".format(alpha[int(m.group(1))-1], repl+10))))
        elif control.name.startswith("No Template Control"):
            c_row = alpha[repl // 3 + 6]
            c_col = repl % 3 + 10
            placements.append((control.stateless, (container, "{0}:{1}".format(c_row, c_col))))
    return placements

def pos_384(row, col, repl):
    return row * 2 + (repl // 2), col * 2 + (repl % 2)

def pos_96(row, col, repl):
    return row, col*3+repl

main(sys.argv[1])

