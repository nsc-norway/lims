import random
import sys
import mock
import unittest
import setups
sys.path.append("../normalisation")

dilution_calculator = __import__("dilution-calculator")

@mock.patch('__builtin__.open', autospec=True)
@mock.patch('dilution-calculator.Lims', autospec=True)
@mock.patch('dilution-calculator.Process', autospec=True)
class DilutionCalculatorTestCase(unittest.TestCase):

    def setUp(self):
        random.seed(13) # Set seed for repeatable test

    def test_success_with_source(self, mock_lims, mock_process, mock_open):

        mock_process_inst = mock_process.return_value
        mock_process_inst.udf = {
                "Show source location": True,
                "Default normalised concentration (nM)": 5.31,
                "Volume to take from inputs": 11.23,
                }

        N = 21
        io_spec = []
        for i in xrange(N):
            io_spec.append((
                    "Pr%dject" % (i//10),
                    "Sam%dple" % i,
                    {'Molarity': random.random() * 20.0},
                    {}
                    ))

        output_file = mock_open.return_value

        FILENAME_PREFIX = "2-111"

        inputs, result_files, input_output_maps = setups.get_input_output(io_spec)
        mock_process_inst.input_output_maps = input_output_maps
        dilution_calculator.main("TEST_LIMSID", FILENAME_PREFIX)

        mock_open.assert_called_with(FILENAME_PREFIX + "_normalisation.csv", "wb") 
        
