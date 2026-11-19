import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.v14_review_seal import seal


class GradeSealTest(unittest.TestCase):
    def test_draft_packet_cannot_be_sealed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'package_manifest.json').write_text('{"ready_for_human_review":false}')
            with self.assertRaisesRegex(ValueError,'draft'):
                seal(p/'responses.csv',p)

    def test_C_failure_restores_the_queue_instead_of_waiting_forever(self):
        from scripts.v14_review_queue import after_c
        with patch('scripts.v14_review_queue.call',return_value='FAILED|'),patch('scripts.v14_review_queue.restore') as restore:
            after_c();restore.assert_called_once()

    def test_successful_C_chain_installs_integrity_failure_guard(self):
        from scripts.v14_review_queue import after_c
        with patch('scripts.v14_review_queue.call',side_effect=['COMPLETED|\nCOMPLETED|','123']) as call,patch('scripts.v14_review_queue.restore') as restore:
            after_c();restore.assert_not_called()
            self.assertIn('--dependency=afterany:61559510',call.call_args.args)

    def test_integrity_failure_restores_bulk_queue(self):
        from scripts.v14_review_queue import after_integrity
        with patch('scripts.v14_review_queue.call',return_value='FAILED|'),patch('scripts.v14_review_queue.restore') as restore:
            after_integrity();restore.assert_called_once()


@unittest.skipUnless(importlib.util.find_spec('reportlab'),'Run with the bundled PDF Python runtime')
class PDFPacketTest(unittest.TestCase):
    def test_regeneration_preserves_human_response_file(self):
        from scripts.v14_review_pdf import response_template
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'responses.csv';path.write_text('human-written-response\n')
            response_template(path,[dict(case_id='B001')],True)
            self.assertEqual(path.read_text(),'human-written-response\n')

    def test_missing_evidence_prevents_release(self):
        from scripts.v14_review_pdf import build_group
        with tempfile.TemporaryDirectory() as tmp,patch('scripts.v14_review_pdf.ready',return_value=(None,[],['pending C'])):
            with self.assertRaisesRegex(ValueError,'not complete'):
                build_group([dict(case_id='B001')],Path(tmp),True,True)
            self.assertFalse(list(Path(tmp).glob('*.pdf')))
