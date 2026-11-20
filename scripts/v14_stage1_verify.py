"""Verify every anonymous PDF page, embedded pixels, ZIP and blank response form.

Image annotation/layout inspection is a separate visual-QA step. This validator
does not mark a package ready, classify candidates, or reveal held identities.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import zipfile

from PIL import Image
from pypdf import PdfReader


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def pixel_hash(image):
    rgb=image.convert('RGB')
    return hashlib.sha256(rgb.tobytes()).hexdigest(),rgb.size


def verify(plan_path,package):
    plan=json.loads(plan_path.read_text());manifest_path=package/'package_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if manifest['input_registration_sha256']!=sha(plan_path):raise ValueError('Wrong assembly plan')
    for name,digest in manifest['artifacts'].items():
        if Path(name).name!=name or sha(package/name)!=digest:raise ValueError('Changed/unsafe package artifact')
    if sha(package/'anonymous_review.zip')!=manifest['zip_sha256']:raise ValueError('ZIP changed')
    expected=['anonymous_review.pdf','blank_review.csv','page_index.csv','README.txt','manifest.json']
    with zipfile.ZipFile(package/'anonymous_review.zip') as archive:
        if sorted(archive.namelist())!=sorted(expected) or archive.testzip():raise ValueError('ZIP entry/CRC policy failed')
        for name in expected[:-1]:
            if archive.read(name)!=(package/name).read_bytes():raise ValueError('ZIP artifact differs')
        inner=json.loads(archive.read('manifest.json'))
        if inner['artifacts']!=manifest['artifacts'] or inner['human_grades_unfilled'] is not True:
            raise ValueError('Inner ZIP manifest differs')
    with (package/'blank_review.csv').open(newline='') as stream:forms=list(csv.DictReader(stream))
    ids=[u['anonymous_id'] for u in plan['units']]
    if ([r['anonymous_id'] for r in forms]!=ids or
            any(r[k].strip() for r in forms for k in ('assessment','confidence','notes'))):
        raise ValueError('Blank response form or alias coverage differs')
    with (package/'page_index.csv').open(newline='') as stream:index=list(csv.DictReader(stream))
    reader=PdfReader(package/'anonymous_review.pdf')
    if reader.is_encrypted or reader.attachments or reader.metadata.get('/Author')!='':
        raise ValueError('Unexpected encryption/attachment/author metadata')
    root=reader.trailer['/Root']
    if any(k in root for k in ('/OpenAction','/AA','/AcroForm')):
        raise ValueError('Unexpected active PDF content')
    if reader.pages[0].images:raise ValueError('Unexpected identity-bearing cover image')
    page_number=1;checked=[]
    for unit,entry in zip(plan['units'],index,strict=True):
        if (entry['anonymous_id']!=unit['anonymous_id'] or int(entry['first_page'])!=page_number+1 or
                int(entry['panels'])!=len(unit['panels'])):raise ValueError('Page navigation differs')
        for ordinal,panel in enumerate(unit['panels'],1):
            page=reader.pages[page_number];images=list(page.images)
            if len(images)!=1 or page.get('/Annots') or page.get('/AA'):
                raise ValueError('Expected exactly one passive raster per evidence page')
            p=Path(panel['path'])
            if sha(p)!=panel['sha256']:raise ValueError('Registered anonymous raster changed')
            with Image.open(p) as image:expected_pixels=pixel_hash(image)
            if pixel_hash(images[0].image)!=expected_pixels:
                raise ValueError('PDF pixels differ from the registered neutral panel')
            text=page.extract_text()
            heading=' / '.join(x for x in (unit['anonymous_id'],panel.get('alternative_label'),f'evidence {ordinal:02d}') if x)
            if heading not in text:raise ValueError('Missing neutral page heading')
            stripped=text.replace(heading,'').replace(
                'Assessment remains blank. Record the unit ID and any alternative-specific notes in the review table.','')
            if stripped.strip()!=str(page_number+1):raise ValueError('Unexpected evidence-page text')
            checked.append(dict(page=page_number+1,anonymous_id=unit['anonymous_id'],
                registered_raster_sha256=panel['sha256'],pixel_roundtrip_verified=True))
            page_number+=1
        if int(entry['last_page'])!=page_number:raise ValueError('Page end differs')
    if page_number!=len(reader.pages) or page_number!=manifest['pages']:
        raise ValueError('Missing or unexpected PDF pages')
    receipt=dict(package_manifest_sha256=sha(manifest_path),plan_sha256=sha(plan_path),
        verifier_sha256=sha(Path(__file__)),pages=len(reader.pages),anonymous_units=len(ids),
        every_evidence_page_pixel_roundtrip_verified=True,neutral_evidence_page_text_verified=True,
        standalone_zip_verified=True,blank_forms_verified=True,pages_checked=checked,
        visual_annotation_layout_QA_complete=False,final_ready_for_human_review=False,
        scope='All-page source/pixel/text/ZIP/form integrity. Source renderer annotation audit and visual full-page inspection remain explicit separate gates; no identity reveal, human grade or final readiness implied.')
    (package/'structural_QA.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(dict(pages=len(reader.pages),anonymous_units=len(ids),pixel_roundtrip=True,final_ready=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--package',type=Path,required=True);args=parser.parse_args();verify(args.plan,args.package)
