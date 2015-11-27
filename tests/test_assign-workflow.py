import unittest
import mock
import sys
import random
from genologics.lims import *
sys.path.append("../helpers")

assign_workflow = __import__("assign-workflow")

class SaveInAnalytesTestCase(unittest.TestCase):

    @mock.patch('assign-workflow.Process', autospec=True)
    @mock.patch('assign-workflow.Lims', autospec=True)
    def test_success(self, mock_lims, mock_process):

        WORKFLOW_NAME = "FooFlow"
        ANALYTES = [mock.sentinel.artifact1, mock.sentinel.artifact2]

        mock_lims.return_value.get_workflows.return_value = [mock.sentinel.workflow_object]
        mock_process.return_value.all_inputs.return_value = ANALYTES

        assign_workflow.main("FooProcess", WORKFLOW_NAME)

        mock_process.return_value.all_inputs.assert_called_with(unique=True)
        mock_lims.return_value.get_workflows.assert_called_once_with(name=WORKFLOW_NAME)
        mock_lims.return_value.route_analytes.assert_called_once_with(ANALYTES, mock.sentinel.workflow_object)

    @mock.patch('assign-workflow.Process', autospec=True)
    @mock.patch('assign-workflow.Lims', autospec=True)
    def test_missing_workflow(self, mock_lims, mock_process):

        WORKFLOW_NAME = "FooFlow"
        ANALYTES = [mock.sentinel.artifact1, mock.sentinel.artifact2]

        mock_lims.return_value.get_workflows.return_value = []
        mock_process.return_value.all_inputs.return_value = ANALYTES

        self.assertRaises(BaseException, assign_workflow.main, "FooProcess", WORKFLOW_NAME)
        self.assertFalse(mock_lims.return_value.route_analytes.called)

    @mock.patch('assign-workflow.Process', autospec=True)
    @mock.patch('assign-workflow.Lims', autospec=True)
    def test_none_workflow(self, mock_lims, mock_process):

        assign_workflow.main("FooProcess", "None")

        self.assertFalse(mock_lims.return_value.route_analytes.called)

