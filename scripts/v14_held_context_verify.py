"""Verify all held context rasters without revealing identities or grading."""
import argparse
from hashlib import file_digest,sha256
import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


def digest(path):
    with path.open('rb') as stream:return file_digest(stream,'sha256').hexdigest()


def pixels(image):
    rgb=image.convert('RGB')
    return rgb.size,sha256(rgb.tobytes()).hexdigest()


def verify(key,package):
    if 'final_private' not in package.parts:raise ValueError('Keep context private')
    held=json.loads(key.read_text());manifest=json.loads((package/'manifest.json').read_text())
    if manifest['inputs'][str(key)]!=digest(key):raise ValueError('Held key changed')
    for name,checksum in manifest['inputs'].items():
        if digest(Path(name))!=checksum:raise ValueError('Held source changed')
    pdf=package/'held_context.pdf'
    if digest(pdf)!=manifest['pdf_sha256']:raise ValueError('Held PDF changed')
    expected=[]
    for unit in held['units']:
        for alternative in unit['alternatives']:
            origin=alternative['origins'][0];path=Path(origin['context_manifest'])
            if digest(path)!=origin['context_manifest_sha256']:raise ValueError('Mode proof changed')
            context=json.loads(path.read_text())
            for name in ('context.png','conditions.png','images.png'):
                image=path.parent/name
                if digest(image)!=context['outputs'][name]:raise ValueError('Mode raster changed')
                expected.append(image)
    reader=PdfReader(pdf)
    if reader.is_encrypted or reader.attachments or any(k in reader.trailer['/Root'] for k in ('/OpenAction','/AA','/AcroForm')):
        raise ValueError('Held PDF must contain passive pages only')
    checked=[];cursor=0
    for index,page in enumerate(reader.pages):
        images=list(page.images)
        if page.get('/Annots') or page.get('/AA') or len(images)>1:
            raise ValueError('Unexpected held page content')
        if not images:
            if not page.extract_text().strip():raise ValueError('Blank held summary page')
            continue
        if cursor>=len(expected):raise ValueError('Unexpected held image')
        with Image.open(expected[cursor]) as image:
            if pixels(image)!=pixels(images[0].image):raise ValueError('Held PDF raster differs')
        checked.append(dict(page=index+1,registered_raster_sha256=digest(expected[cursor])))
        cursor+=1
    if cursor!=len(expected) or len(reader.pages)!=manifest['pages']:
        raise ValueError('Incomplete held alternative/page coverage')
    receipt=dict(pdf_sha256=digest(pdf),key_sha256=digest(key),verifier_sha256=digest(Path(__file__)),
        pages=len(reader.pages),units=len(held['units']),image_pages=cursor,
        every_held_image_pixel_roundtrip_verified=True,checked=checked,
        identity_revealed=False,human_grades_filled=False,full_page_visual_QA_complete=False)
    (package/'structural_QA.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(dict(held_pages=len(reader.pages),held_images=cursor,pixel_roundtrip=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key',type=Path,required=True);parser.add_argument('--package',type=Path,required=True)
    args=parser.parse_args();verify(args.key,args.package)
