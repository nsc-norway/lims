import unittest
import mock
import sys
from genologics.lims import *
sys.path.append("../archive-reagents")

# Test for 
#    - archive-reagents.py
#    - archive-hiseq.py

# Made into one test script, because they are very similar

archive_reagents = __import__("archive-reagents")
archive_hiseq = __import__("archive-hiseq")

@mock.patch('archive-reagents.Step', autospec=True)
@mock.patch('archive-reagents.Lims', autospec=True)
class ArchiveReagentsTestCase(unittest.TestCase):

    def test_archive_reagents_with_reagents(self, mock_lims, mock_step):
        N = 3
        mylots = [
                mock.create_autospec(ReagentLot, instance=True)
                for i in xrange(N)
                ]
        mock_step.return_value.reagentlots.reagent_lots = mylots

        archive_reagents.main("Dummy-ProcessId")

        for lot in mylots:
            self.assertEquals(lot.status, "ARCHIVED")
            lot.put.assert_called_once_with()

    def test_archive_reagents_no_reagents(self, mock_lims, mock_step):
        mock_step.return_value.reagentlots.reagent_lots = []
        archive_reagents.main("Dummy-ProcessId")
        # Check that it doesn't crash


@mock.patch('archive-hiseq.Step', autospec=True)
@mock.patch('archive-hiseq.Lims', autospec=True)
class ArchiveHiseqTestCase(unittest.TestCase):

    def test_archive_hiseq_no_reagents(self, mock_lims, mock_step):
        mock_step.return_value.reagentlots.reagent_lots = []
        archive_hiseq.main("Dummy-ProcessId")
        # Check that it doesn't crash

    def test_archive_hiseq(self, mock_lims, mock_step):
        N = 3
        DUMMY = 1
        mylots = [
                mock.create_autospec(ReagentLot, instance=True)
                for i in xrange(N)
                ]
        mylots[DUMMY].lot_number = "Rapid dummy"
        mock_step.return_value.reagentlots.reagent_lots = mylots

        archive_hiseq.main("Dummy-ProcessId")

        for i, lot in enumerate(mylots):
            if i != DUMMY:
                self.assertEquals(lot.status, "ARCHIVED")
                lot.put.assert_called_once_with()
            else:
                self.assertNotEquals(lot.status, "ARCHIVED")
                self.assertFalse(lot.put.called)
