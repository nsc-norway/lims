import unittest
import mock
import sys
import random
from genologics.lims import *
sys.path.append("../normalisation")

dilution_calculator = __import__("dilution-calculator")

@mock.patch('dilution-calculator.Process', autospec=True)
@mock.patch('dilution-calculator.Lims', autospec=True)
class DilutionCalculatorTestCase(unittest.TestCase):

    def setUp(self):
        random.seed(13) # Set seed for repeatable test

    def test_core(self, mock_lims, mock_process):
        pass

    def test_success_with_source(self, mock_lims, mock_process):

        input_output_maps = []
        N = 21
        FILENAME_PREFIX = "2-111"

        inputs = []
        nonshared_outputs = []

        mock_process_inst = mock_process.return_value
        mock_process_inst.udf = {
                "Show source location": True
                }

        for i in xrange(N):
            output = mock.create_autospec(Artifact, instance=True)
            input = mock.create_autospec(Artifact, instance=True)
            input.udf = {
                    "": ""
                    }
            inputs.append(input)
            output.udf = {
                    "": ""
                    }
            nonshared_outputs.append(output)
            
            input_output_maps.append((
                {'uri': input},
                {'uri': output, 'output-generation-type': 'PerInput', 'output-type': 'ResultFile'}
                ))

        shared_result_file = mock.create_autospec(Artifact)
        for i in xrange(N):
            input_output_maps.append((
                {'uri': input},
                {'uri': shared_result_file, 'output-generation-type': 'PerAllInputs', 'output-type': 'ResultFile'}
                ))


        # Shuffle list
        random.shuffle(input_output_maps)
        mock_process_inst.input_output_maps = input_output_maps

        dilution_calculator.main("TEST_LIMSID", FILENAME_PREFIX)

        
