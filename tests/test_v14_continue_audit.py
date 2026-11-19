import contextlib
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import yaml

from ls_satsearch.run import read_csv, sha, write_csv
from scripts import v14_continue_audit as audit


class ContinuationAuditTest(unittest.TestCase):
    @contextlib.contextmanager
    def workspace(self):
        previous=Path.cwd()
        with TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                Path('logs').mkdir()
                Path('logs/v14-dispatch.json').write_text(json.dumps(dict(a=[dict(job='616')],b=[dict(job='617')])))
                for cohort,names in (('a',('a0','a1','a2')),('b',('b0','b1'))):
                    folder=Path(f'configs/v14/cohorts/{cohort}');folder.mkdir(parents=True)
                    (folder/'fields.yaml').write_text(yaml.safe_dump(dict(fields=[dict(id=n) for n in names])))
                old=Path('results/v14/progress_20261118');old.mkdir(parents=True)
                write_csv(old/'retry_manifest.csv',[dict(cohort='a',index=1,field='a1'),
                          dict(cohort='b',index=0,field='b0'),dict(cohort='a',index=0,field='a0')])
                output=Path('output');output.mkdir()
                write_csv(output/'fields.csv',[dict(cohort=c,index=i,field=f,status=s) for c,i,f,s in
                          [('a',0,'a0','complete'),('a',1,'a1','missing'),('a',2,'a2','prepared'),
                           ('b',0,'b0','missing'),('b',1,'b1','no_usable_gr')]])
                yield output
            finally:
                os.chdir(previous)

    def test_accepts_results_and_preserves_live_work_before_retrying_terminal_gaps(self):
        text='JobID|JobName|State\n616_0|ls14-a|FAILED\n617_0|ls14-b|PENDING\n61510268_0|ls14-retry|RUNNING\n'
        with self.workspace() as output, patch.object(audit.subprocess,'check_output',side_effect=[text,'']),contextlib.redirect_stdout(io.StringIO()):
            audit.run(output)
            actions={r['field']:r['action'] for r in read_csv(output/'retry_followup.csv')}
            self.assertEqual(actions,dict(a0='accepted_manifest',a1='covered_by_live_job',
                                         a2='submit_retry',b0='covered_by_live_job'))
            self.assertEqual([r['field'] for r in read_csv(output/'uncovered_retries.csv')],['a2'])

    def test_unknown_slurm_state_cannot_trigger_a_duplicate_retry(self):
        text='JobID|JobName|State\n616_0|ls14-a|UNRECOGNIZED\n'
        with self.workspace() as output,patch.object(audit.subprocess,'check_output',side_effect=[text,'']):
            with self.assertRaisesRegex(ValueError,'Unresolved Slurm state'):
                audit.run(output)

    def test_live_scheduler_covers_retry_missing_from_accounting(self):
        accounting='JobID|JobName|State\n616_0|ls14-a|TIMEOUT\n617_0|ls14-b|PENDING\n'
        queue='61510268_0|ls14-retry|PENDING|Priority|0:00\n'
        with self.workspace() as output,patch.object(audit.subprocess,'check_output',side_effect=[accounting,queue]),contextlib.redirect_stdout(io.StringIO()):
            audit.run(output)
            actions={r['field']:r['action'] for r in read_csv(output/'retry_followup.csv')}
            self.assertEqual(actions['a1'],'covered_by_live_job')
            self.assertEqual([r['field'] for r in read_csv(output/'uncovered_retries.csv')],['a2'])

    def test_registered_second_retry_is_not_submitted_again(self):
        accounting='JobID|JobName|State\n616_0|ls14-a|TIMEOUT\n617_0|ls14-b|PENDING\n'
        queue='61510268_0|ls14-retry|PENDING|Priority|0:00\n777_0|ls14-retry-new|PENDING|Priority|0:00\n'
        with self.workspace() as output:
            path=Path('retry2.csv');write_csv(path,[dict(cohort='a',index=2,field='a2')])
            Path('logs/v14-retry-jobs.json').write_text(json.dumps({'777':dict(manifest=str(path),sha256=sha(path))}))
            with patch.object(audit.subprocess,'check_output',side_effect=[accounting,queue]),contextlib.redirect_stdout(io.StringIO()):
                audit.run(output)
            self.assertEqual(read_csv(output/'uncovered_retries.csv'),[])
            path.write_text(path.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'changed retry'):
                audit.run(output)
