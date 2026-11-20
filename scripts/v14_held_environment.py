"""Bind frozen known/environment annotations to the held review units."""
import argparse
import csv
from hashlib import file_digest
import json
from pathlib import Path
import textwrap

from pypdf import PdfReader
from reportlab.lib.pagesizes import landscape,A4
from reportlab.pdfgen import canvas

RECORDS=Path('results/v14/production_integration/reconciled/qualified_discovery_records.csv')
FRAME=Path('results/v14/human_review/final_private/final_population/registration.json')
FIELDS=('known_system','nearest_known_position','nearest_known_position_arcmin',
        'known_environment_context','extended_galaxy_context','context_from_catalogue')


def digest(path):
    with path.open('rb') as stream:return file_digest(stream,'sha256').hexdigest()


def ascii_text(value):
    return str(value).encode('ascii','backslashreplace').decode('ascii')


def build(key,output):
    if 'final_private' not in output.parts:raise ValueError('Keep environments private before sealing')
    frozen=json.loads(FRAME.read_text())
    if frozen['inputs'][str(RECORDS)]!=digest(RECORDS):raise ValueError('Frozen production metadata changed')
    with RECORDS.open(newline='') as stream:records={r['detection_id']:r for r in csv.DictReader(stream)}
    units=json.loads(key.read_text())['units'];inputs={str(p):digest(p) for p in (key,RECORDS,FRAME)}
    output.mkdir(parents=True,exist_ok=False);pdf=output/'held_environments.pdf'
    width,height=landscape(A4);margin=28;doc=canvas.Canvas(str(pdf),pagesize=(width,height),pageCompression=1)
    doc.setAuthor('');doc.setTitle('Held source-bound environments')
    doc.setFont('Helvetica-Bold',19);doc.drawString(margin,height-45,'Held source-bound environments')
    lines=['WITHHELD until actual anonymous user responses are sealed.',
        'Exact frozen production records, including every source linked to each review unit.',
        'Catalogue associations and environments are annotations, not physical classifications.',
        'Missing annotations mean not recorded; proximity alone does not establish membership.',
        'See held_context.pdf for all C modes, contribution images and observing conditions.',
        'The independent-imaging campaign and its measured limits remain in fourteenth_science_report.md.',
        'No new candidate grade, independent confirmation or human assessment is inferred.']
    doc.setFont('Helvetica',11)
    for i,line in enumerate(lines):doc.drawString(margin,height-90-24*i,line)
    doc.showPage();index=[];expected=[]
    for unit in units:
        alias=unit['anonymous_id'];first=doc.getPageNumber();doc.bookmarkPage(alias);doc.addOutlineEntry(alias,alias)
        y=height-55
        def heading():
            doc.setFont('Helvetica-Bold',14);doc.drawString(margin,height-30,alias+' / held environments')
        def line(value):
            nonlocal y
            for part in textwrap.wrap(ascii_text(value),120,break_long_words=True) or ['']:
                if y<40:
                    doc.showPage();heading();y=height-55
                doc.setFont('Helvetica',9);doc.drawString(margin,y,part);expected.append(part);y-=13
        heading();line('Prior exposed case references: '+(', '.join(unit['old_ids']) or 'not recorded'))
        if unit['control']:
            line('Known weak control: '+unit['control']+'; separate from the production frame.')
        if unit['selection']:
            line('Frozen region: '+unit['selection']['region'])
        for identity in unit['production_record_ids']:
            row=records[identity];line('Original qualified record: '+identity)
            line('Field='+row['field']+'; RA='+row['ra_deg']+'; Dec='+row['dec_deg'])
            for field in FIELDS:line(field+' = '+(row[field].strip() or 'not recorded'))
            line('Original source table: '+row['input']+'; SHA256='+row['source_sha256'])
            y-=6
        index.append(dict(anonymous_id=alias,first_page=first,last_page=doc.getPageNumber(),
                          production_records=len(unit['production_record_ids'])))
        doc.showPage()
    doc.save()
    for name,checksum in inputs.items():
        if digest(Path(name))!=checksum:raise ValueError('Held metadata changed during assembly')
    reader=PdfReader(pdf);text='\n'.join(page.extract_text() for page in reader.pages)
    if (reader.attachments or any(page.get('/Annots') for page in reader.pages)
            or any(part not in text for part in expected)):
        raise ValueError('Held annotation coverage or passive-page check failed')
    receipt=dict(inputs=inputs,pdf_sha256=digest(pdf),code_sha256=digest(Path(__file__)),
        units=len(units),pages=len(reader.pages),source_records=sum(len(u['production_record_ids']) for u in units),
        environment_fields=list(FIELDS),every_rendered_annotation_text_verified=True,page_index=index,
        identity_revealed=False,human_grades_filled=False,all_page_render_layout_QA_pending=True,
        scope='Held exact-record catalogue/environment appendix. Complements the observing-condition figures; catalogue absence/proximity is not confirmation or a physical class. No independent imaging measurement or human grade generated.')
    (output/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(dict(environment_units=len(units),environment_pages=len(reader.pages),production_records=receipt['source_records']),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--key',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();build(args.key,args.output)
