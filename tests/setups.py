import mock
import random
from genologics.lims import *


def get_well(i_well):
    rows = "ABCDEFGH"
    return rows[i_well % 8] + ":" + str(1 + i_well//8)
    

def get_input_qc(io_spec, shared=1):
    """Get the "input_output_maps" to give to a QC process.
    
    use io_spec to define the UDFs of the mock artifacts.
    io_spec is a list, one element for each input/measurement (ResultFile) pair.
    
    Each element is a tuple with three elements, containing the input's 
    name, and dicts for the input and out UDFs respectively.
    
    io_spec = [
        (project_name, name, {'udf':'value1', ...}, {'measurement_udf': 111, ...}), # Input, ResultFile 1
        (project_name, name, {'udf':'value2', ...}, {'measurement_udf': 131, ...}), # Input, ResultFile 2
        ...
    ]

    Returns the lists of generated inputs and measurements in corresponding lists, 
    and the input_output_maps data structure which can be assigned to a process.
    """

    inputs = []
    nonshared_outputs = []
    input_output_maps = []

    i_cont = 0
    i_well = 0
    for project, name, input_udfs, output_udfs in io_spec:
        if i_cont == 0 or i_well == 96 or random.random() > 0.95:
            input_container = mock.create_autospec(Container, instance=True)
            input_container.name = "InputContainer%d" % (i_cont)
            i_cont += 1
            i_well = 0

        i_well += 1
        output = mock.create_autospec(Artifact, instance=True)
        input = mock.create_autospec(Artifact, instance=True)
        input.location = (input_container, get_well(i_well))
        input.udf = dict(input_udfs)
        inputs.append(input)
        output.udf = dict(output_udfs)
        nonshared_outputs.append(output)
        
        input_output_maps.append((
            {'uri': input},
            {'uri': output, 'output-generation-type': 'PerInput', 'output-type': 'ResultFile'}
            ))

    shared_result_files = [mock.create_autospec(Artifact) for i in xrange(shared)]
    for io in io_spec:
        for shared_file in shared_result_files:
            shared_rec = (
                {'uri': input},
                {'uri': shared_result_file, 'output-generation-type': 'PerAllInputs', 'output-type': 'ResultFile'}
                )
            input_output_maps.append(shared_rec)

    random.shuffle(input_output_maps)
    return inputs, nonshared_outputs, input_output_maps
    
    
def get_input_output(io_spec, shared=1):
    """Get the "input_output_maps" to give to a transformation process.
    
    io_spec is the same as in the above method, but this time the outputs are analytes.
    """


    inputs = []
    nonshared_outputs = []
    input_output_maps = []

    i_cont = 0
    i_well = 0
    for project, name, input_udfs, output_udfs in io_spec:
        if i_cont == 0 or i_well == 96 or random.random() > 0.95:
            output_container = mock.create_autospec(Container, instance=True)
            output_container.name = "Container%d" % (i_cont)
            input_container = mock.create_autospec(Container, instance=True)
            input_container.name = "InputContainer%d" % (i_cont)
            i_cont += 1
            i_well = 0

        i_well += 1
        sample = mock.create_autospec(Sample, instance=True)
        sample.project = mock.create_autospec(Project, instance=True)
        sample.project.name = project

        output = mock.create_autospec(Artifact, instance=True)
        output.location = (output_container, get_well(96 - i_well))
        output.name = "O" + name
        output.samples = [sample]
        output.udf = dict(output_udfs)
        nonshared_outputs.append(output)
        input = mock.create_autospec(Artifact, instance=True)
        input.location = (input_container, get_well(i_well))
        input.udf = dict(input_udfs)
        input.name = "I" + name
        input.samples = [sample]
        inputs.append(input)
        
        input_output_maps.append((
            {'uri': input},
            {'uri': output, 'output-generation-type': 'PerInput', 'output-type': 'Analyte'}
            ))

    shared_result_files = [mock.create_autospec(Artifact) for i in xrange(shared)]
    for io in io_spec:
        for shared_file in shared_result_files:
            shared_rec = (
                {'uri': input},
                {'uri': shared_file, 'output-generation-type': 'PerAllInputs', 'output-type': 'ResultFile'}
                )
            input_output_maps.append(shared_rec)

    random.shuffle(input_output_maps)
    return inputs, nonshared_outputs, input_output_maps



