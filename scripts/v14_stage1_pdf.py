"""Assemble score-hidden review figures; release readiness is a separate QA gate.

Reads only registered diagnostic rasters, never source catalogues or C scores.
Use the bundled PDF runtime. Pilot output must remain in final_private.
"""
import argparse
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import zipfile
from PIL import Image
from reportlab.lib.pagesizes import landscape,A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def digest(path):return sha256(path.read_bytes()).hexdigest()


def build(source,output):
    plan=json.loads(source.read_text())
    if plan.get('pilot'):
        if 'final_private' not in output.parts:raise ValueError('Private pilot cannot become a public release')
    elif not plan.get('final_population_frozen'):
        raise ValueError('Full production and sampling population must be frozen before final assembly')
    units=plan['units'];ids=[u['anonymous_id'] for u in units]
    if len(ids)!=len(set(ids)) or not all(re.fullmatch(r'A\d{4}',x) for x in ids):
        raise ValueError('Anonymous unit labels must be unique neutral IDs')
    for u in units:
        for panel in u['panels']:
            p=Path(panel['path'])
            if digest(p)!=panel['sha256']:raise ValueError('Registered raster changed')
            with Image.open(p) as im:im.verify()
    output.mkdir(parents=True,exist_ok=False)
    pdf=output/'anonymous_review.pdf';width,height=landscape(A4);margin=28
    doc=canvas.Canvas(str(pdf),pagesize=(width,height),pageCompression=1)
    doc.setTitle('Anonymous photometric review');doc.setAuthor('');doc.setSubject('Unweighted observed evidence; identities and model scores withheld')
    doc.setCreator('Legacy Satellite Search review assembly')
    doc.setFont('Helvetica-Bold',20);doc.drawString(margin,height-50,'Anonymous photometric review')
    lines=[
        'PRIVATE PREPARATION PILOT - not the final human review' if plan.get('pilot') else 'Frozen project-wide review materials',
        'Judge observed morphology, colour-magnitude coherence and spatial concentration.',
        'Record one assessment per anonymous unit; use notes for different hypotheses.',
        'Allowed assessments: unassessable / artefact_or_background / uncertain / follow_up.',
        'Confidence and notes are optional. No human assessment has been pre-filled.',
        'Alternative labels follow a neutral order; they do not indicate model rank.',
        'Wide mosaics may be resampled. Use central stamps for source morphology;',
        'display sampling is not seeing. Count bars are not detection significance.',
        'Panels use the same imaging and are not independent confirmation.',
        'Identities, absolute coordinates, model probabilities, scores and environments',
        'remain in the held second phase until actual responses are sealed.',
        'Previously exposed cases are retained; this does not restore prospective blindness.',
    ]
    doc.setFont('Helvetica',11)
    for i,line in enumerate(lines):doc.drawString(margin,height-90-23*i,line)
    doc.showPage();index=[]
    for u in units:
        first=doc.getPageNumber();label=u['anonymous_id']
        doc.bookmarkPage(label);doc.addOutlineEntry(label,label,0)
        for ordinal,panel in enumerate(u['panels'],1):
            doc.setFont('Helvetica-Bold',13);doc.drawString(margin,height-27,f'{label} / evidence {ordinal:02d}')
            with Image.open(panel['path']) as im:
                # Embed pixels only; neither source filename nor PNG metadata enter PDF.
                rgb=im.convert('RGB');iw,ih=rgb.size
                scale=min((width-2*margin)/iw,(height-90)/ih)
                dw,dh=iw*scale,ih*scale
                doc.drawImage(ImageReader(rgb),(width-dw)/2,height-45-dh,width=dw,height=dh)
            doc.setFont('Helvetica',8)
            doc.drawString(margin,20,'Assessment remains blank. Record the unit ID and any alternative-specific notes in the review table.')
            doc.drawRightString(width-margin,20,str(doc.getPageNumber()))
            doc.showPage()
        index.append(dict(anonymous_id=label,first_page=first,last_page=doc.getPageNumber()-1,panels=len(u['panels'])))
    doc.save()
    for name,keys,rows in [
        ('blank_review.csv',['anonymous_id','assessment','confidence','notes'],[dict(anonymous_id=x) for x in ids]),
        ('page_index.csv',['anonymous_id','first_page','last_page','panels'],index)]:
        with (output/name).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    readme=output/'README.txt'
    readme.write_text('Open anonymous_review.pdf and record one assessment per unit in blank_review.csv.\n'
                      'page_index.csv provides navigation. No identities or source keys are included.\n'
                      'This is private preparation only.\n' if plan.get('pilot') else
                      'Open anonymous_review.pdf and use blank_review.csv; identities remain withheld until responses are sealed.\n')
    content=[pdf,output/'blank_review.csv',output/'page_index.csv',readme]
    blind_manifest=dict(units=len(units),pages=1+sum(len(u['panels']) for u in units),
                        artifacts={p.name:digest(p) for p in content},human_grades_unfilled=True,
                        pilot=bool(plan.get('pilot')),final_ready_for_human_review=False)
    archive=output/'anonymous_review.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in content:z.write(p,p.name)
        z.writestr('manifest.json',json.dumps(blind_manifest,indent=2)+'\n')
    blind_manifest.update(zip_sha256=digest(archive),input_registration_sha256=digest(source),
                          assembly_sha256=digest(Path(__file__)),scope='Assembled materials only; privacy, full-page QA and final delivery gates are separate. Source keys and held context are excluded.')
    (output/'package_manifest.json').write_text(json.dumps(blind_manifest,indent=2)+'\n')
    print(json.dumps(dict(units=len(units),pages=blind_manifest['pages'],final_ready=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();build(a.input,a.output)
