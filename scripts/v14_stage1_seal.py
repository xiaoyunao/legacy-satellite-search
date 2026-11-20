"""Seal actual project-wide user responses; never grade or reveal identities."""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

ASSESSMENTS = {'unassessable', 'artefact_or_background', 'uncertain', 'follow_up'}


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def seal(responses, package, delivery_status, reviewer):
    manifest_path = package/'package_manifest.json'
    before = {p: digest(p) for p in (responses, manifest_path, delivery_status)}
    manifest = json.loads(manifest_path.read_text())
    status = json.loads(delivery_status.read_text())
    if (manifest.get('pilot') or not manifest.get('final_ready_for_human_review')
            or not status.get('final_ready_for_human_review')):
        raise ValueError('Draft/pilot materials cannot be sealed or revealed')
    if not reviewer.strip():
        raise ValueError('Identify the actual human reviewer')
    for name, checksum in manifest['artifacts'].items():
        if Path(name).name != name or digest(package/name) != checksum:
            raise ValueError('Released artifact changed: '+name)
    if digest(package/'anonymous_review.zip') != manifest['zip_sha256']:
        raise ValueError('Released standalone ZIP changed')
    expected = read(package/'blank_review.csv')
    if any(row.get(k, '').strip() for row in expected
           for k in ('assessment', 'confidence', 'notes')):
        raise ValueError('Released response form was not blank')
    rows = read(responses)
    ids = [row['anonymous_id'] for row in expected]
    if (len(rows) != len(ids) or len({r['anonymous_id'] for r in rows}) != len(ids)
            or {r['anonymous_id'] for r in rows} != set(ids)):
        raise ValueError('Responses must cover exactly the released anonymous units')
    if any(r.get('assessment', '') not in ASSESSMENTS for r in rows):
        raise ValueError('Every unit needs an actual user assessment')
    if any(digest(p) != checksum for p, checksum in before.items()):
        raise ValueError('Responses or release changed during validation')
    path = responses.with_suffix('.sealed.json')
    receipt = dict(utc=datetime.now(timezone.utc).isoformat(), reviewer=reviewer,
        responses_sha256=digest(responses), package_manifest_sha256=digest(manifest_path),
        phase1_pdf_sha256=manifest['artifacts']['anonymous_review.pdf'],
        zip_sha256=manifest['zip_sha256'], delivery_status_sha256=digest(delivery_status),
        units=len(rows), identity_revealed=False,
        scope='User-supplied assessments sealed without alteration. No grades inferred; identity/context reveal is a subsequent separate step.')
    # Exclusive creation preserves a previous seal, including under concurrent calls.
    with path.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('responses', type=Path)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--delivery-status', type=Path,
                        default=Path('results/v14/human_review/final_delivery_status.json'))
    parser.add_argument('--reviewer', required=True)
    args = parser.parse_args()
    print(seal(args.responses, args.package, args.delivery_status, args.reviewer))
