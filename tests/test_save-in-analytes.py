import unittest
import mock
import sys
from genologics.lims import *
sys.path.append("../aggregate-qc")

save_in_analytes = __import__("save-in-analytes")

class SaveInAnalytesTestCase(unittest.TestCase):


    @mock.patch('save-in-analytes.Process', autospec=True)
    @mock.patch('save-in-analytes.Lims', autospec=True)
    def test_success(self, mock_lims, mock_process):

        N = 27
        INT_FIELD_NAME = "Test1"
        STRING_FIELD_NAME = "Test2"
        EXISTING_FIELD_NAME = "Test3"

        # I/O map of a QC process:
        #  in1 -> ResultFile1
        #  in1 -> SharedResultFile
        #  in2 -> ResultFile2
        #...

        mock_process.return_value.input_output_maps = []
        inputs = []
        nonshared_outputs = []

        for i in xrange(N):
            output = mock.create_autospec(Artifact, instance=True)
            input = mock.create_autospec(Artifact, instance=True)
            input.udf = {
                    EXISTING_FIELD_NAME: i * 432
                    }
            inputs.append(input)
            output.udf = {
                    INT_FIELD_NAME: i * 433,
                    STRING_FIELD_NAME: "foo%dbar" % i
                    }
            nonshared_outputs.append(output)
            
            mock_process.return_value.input_output_maps.append((
                {'uri': input},
                {'uri': output, 'output-generation-type': 'PerInput', 'output-type': 'ResultFile'}
                ))

        shared_result_file = mock.create_autospec(Artifact)
        for i in xrange(N):
            mock_process.return_value.input_output_maps.append((
                {'uri': input},
                {'uri': shared_result_file, 'output-generation-type': 'PerAllInputs', 'output-type': 'ResultFile'}
                ))

        save_in_analytes.main("TEST_LIMSID", [INT_FIELD_NAME, STRING_FIELD_NAME])


        for i in xrange(N):
            expected = {
                    INT_FIELD_NAME: i * 433,
                    STRING_FIELD_NAME: "foo%dbar" % i,
                    EXISTING_FIELD_NAME: i * 432,
                    }
            self.assertEquals(inputs[i].udf, expected)


        mock_lims.return_value.put_batch.assert_called_once_with(mock.ANY) # Check below
        args, kwargs = mock_lims.return_value.put_batch.call_args
        self.assertEqual(set(args[0]), set(inputs))
        
        
    @mock.patch('save-in-analytes.Process', autospec=True)
    @mock.patch('save-in-analytes.Lims', autospec=True)
    def test_missing_value(self, mock_lims, mock_process):

        N = 27
        MISSING_VALUE_INDEX = 3
        STRING_FIELD_NAME = "Test2"

        mock_process.return_value.input_output_maps = []
        inputs = []
        nonshared_outputs = []

        for i in xrange(N):
            output = mock.create_autospec(Artifact, instance=True)
            input = mock.create_autospec(Artifact, instance=True)
            input.udf = {}
            inputs.append(input)
            if i != MISSING_VALUE_INDEX:
                output.udf = {
                        STRING_FIELD_NAME: "foo%dbar" % i
                        }
            else:
                output.udf = {
                        }
            nonshared_outputs.append(output)
            mock_process.return_value.input_output_maps.append((
                {'uri': input},
                {'uri': output, 'output-generation-type': 'PerInput', 'output-type': 'ResultFile'}
                ))

        shared_result_file = mock.create_autospec(Artifact)
        for i in xrange(N):
            mock_process.return_value.input_output_maps.append((
                {'uri': input},
                {'uri': shared_result_file, 'output-generation-type': 'PerAllInputs', 'output-type': 'ResultFile'}
                ))

        self.assertRaises(SystemExit, save_in_analytes.main, "TEST_LIMSID", [STRING_FIELD_NAME])
        
        assert not mock_lims.return_value.put_batch.called


