"""Seal user-filled anonymous grades before preparing identity-reveal material."""
import argparse
import csv
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path


REQUIRED=('reviewer','reviewed_utc','morphology','CMD','spatial','technical_concern','confidence','comments')


def seal(responses,package):
    manifest=json.loads((package/'package_manifest.json').read_text())
    if not manifest['ready_for_human_review']:raise ValueError('Cannot seal a draft review package')
    phase1=manifest['packages']['blind_phase1']
    if sha256(Path(phase1['file']).read_bytes()).hexdigest()!=phase1['sha256']:
        raise ValueError('Released phase-1 PDF differs from its manifest')
    with responses.open() as f:rows=list(csv.DictReader(f))
    wanted={f'B{i:03d}' for i in range(1,36)}
    if len(rows)!=35 or {r['case_id'] for r in rows}!=wanted:
        raise ValueError('Expected exactly the 35 frozen B IDs')
    missing=[r['case_id'] for r in rows if any(not r.get(k,'').strip() for k in REQUIRED)]
    if missing:raise ValueError('Human responses incomplete: '+','.join(missing))
    path=responses.with_suffix('.sealed.json')
    if path.exists():raise ValueError('An existing seal is immutable; preserve it and use a new response file')
    path.write_text(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),
        responses_sha256=sha256(responses.read_bytes()).hexdigest(),
        phase1_pdf_sha256=manifest['packages']['blind_phase1']['sha256'],
        shortlist_manifest_sha256=manifest['shortlist_manifest_sha256'],positions=35,
        scope='User-supplied phase-1 responses sealed. No grades were inferred or filled automatically. Identity reveal and scientific interpretation are a separate subsequent step.'),indent=2)+'\n')
    print(path)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('responses',type=Path)
    parser.add_argument('--package',type=Path,default=Path('results/v14/human_review'))
    args=parser.parse_args();seal(args.responses,args.package)
