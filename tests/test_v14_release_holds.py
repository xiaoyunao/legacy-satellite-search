import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.v14_release_holds import release


class HandoffFallbackTest(unittest.TestCase):
    def test_only_original_pending_user_holds_are_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Path(tmp)/'handoff.json'
            ledger.write_text(json.dumps(dict(original_arrays=['123','124'])))
            with patch('scripts.v14_release_holds.subprocess.check_output',side_effect=[
                    '123_0|PENDING|(JobHeldUser)\n','124_0|RUNNING|node\n']),patch(
                    'scripts.v14_release_holds.subprocess.run') as command:
                release(ledger)
                command.assert_called_once_with(['scontrol','release','123'],check=True)
            self.assertTrue(json.loads(ledger.read_text())['fallback_checked'])

    def test_completed_or_normally_queued_originals_are_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Path(tmp)/'handoff.json'
            ledger.write_text(json.dumps(dict(original_arrays=['123','124'])))
            with patch('scripts.v14_release_holds.subprocess.check_output',side_effect=[
                    '','124_0|PENDING|(Priority)\n']),patch(
                    'scripts.v14_release_holds.subprocess.run') as command:
                release(ledger);command.assert_not_called()
