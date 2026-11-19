"""Render every assembled PDF page and gate human release on recorded layout QA.

First run renders and writes contact sheets; inspect the actual images. Run
--approve-layout only after checking all contact sheets and representative full
pages. This approves presentation/privacy, never scientific candidate grades.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from PIL import Image,ImageDraw,ImageStat
from pypdf import PdfReader

if __package__:
    from .v14_review_pdf import read,ROOT,validate_registration
else:
    from v14_review_pdf import read,ROOT,validate_registration


def digest(path):return sha256(path.read_bytes()).hexdigest()


def run(package,work,approve=False):
    validate_registration()
    manifest_path=package/'package_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if not manifest.get('materials_complete'):raise ValueError('The complete 75-object cohort is required for release QA')
    work.mkdir(parents=True,exist_ok=True)
    cases=read(ROOT/'cases.csv');qa=dict(pdfs={},scope='Presentation and privacy checks only; no science grades.')
    for name,entry in manifest['packages'].items():
        pdf=Path(entry['file'])
        if digest(pdf)!=entry['sha256']:raise ValueError('PDF changed after assembly')
        reader=PdfReader(pdf)
        if len(reader.pages)!=entry['pages']:raise ValueError('Page count mismatch')
        expected={r['case_id'] for r in cases if (r['queue']!='priority')==(name=='blind_phase1')}
        if {r['case_id'] for r in entry['page_index']}!=expected:raise ValueError('Registered positions missing')
        for r in entry['page_index']:
            text=reader.pages[r['first_page']-1].extract_text()
            if r['case_id'] not in text:raise ValueError('Wrong case pagination')
        if name=='blind_phase1':
            text='\n'.join(p.extract_text() for p in reader.pages)
            forbidden={r[k] for r in cases for k in ('field','cohort','candidate_id','source_group_id') if r.get(k)}
            if any(value in text for value in forbidden):raise ValueError('Anonymous PDF text leaks identity')
        prefix=work/name
        pages=sorted(work.glob(name+'-*.png'))
        index_file=work/f'{name}-render_input.json'
        if not (index_file.is_file() and json.loads(index_file.read_text()).get('pdf_sha256')==entry['sha256'] and len(pages)==len(reader.pages)):
            subprocess.run(['pdftoppm','-r','65','-png',str(pdf),str(prefix)],check=True)
            pages=sorted(work.glob(name+'-*.png'))
            index_file.write_text(json.dumps(dict(pdf_sha256=entry['sha256']))+'\n')
        if len(pages)!=len(reader.pages):raise ValueError('Raster pages missing')
        for path in pages:
            with Image.open(path).convert('RGB') as im:
                # A blank render is a hard error; content quality still needs
                # inspection of the contact sheets and full-page images.
                if max(ImageStat.Stat(im).stddev)<1:raise ValueError(f'Blank rendered page {path}')
        contacts=[]
        for start in range(0,len(pages),12):
            contact=Image.new('RGB',(1020,1040),'#dde2e5');draw=ImageDraw.Draw(contact)
            for j,path in enumerate(pages[start:start+12]):
                with Image.open(path).convert('RGB') as im:
                    im.thumbnail((330,235));x=(j%3)*340+(340-im.width)//2;y=(j//3)*260+19
                    contact.paste(im,(x,y));draw.text(((j%3)*340+8,(j//3)*260+3),f'{name} page {start+j+1}',fill='black')
            dest=work/f'{name}-contact-{start//12+1:02d}.jpg';contact.save(dest,quality=90);contacts.append(str(dest))
        qa['pdfs'][name]=dict(sha256=entry['sha256'],pages=len(pages),contact_sheets=contacts)
    qa['contact_sheets_inspected']=bool(approve)
    qa['representative_full_pages_inspected']=bool(approve)
    qa['human_scientific_grades_entered']=False
    (work/'QA.json').write_text(json.dumps(qa,indent=2)+'\n')
    if approve:
        manifest.update(render_QA_complete=True,ready_for_human_review=True,
                        layout_QA=dict(pdfs={k:dict(sha256=v['sha256'],pages=v['pages']) for k,v in qa['pdfs'].items()},
                                       scope=qa['scope'],contact_sheets_inspected=True,representative_full_pages_inspected=True))
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print({k:v['pages'] for k,v in qa['pdfs'].items()},'layout approved' if approve else 'inspect all contact sheets before approval')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path('results/v14/human_review'))
    parser.add_argument('--work',type=Path,default=Path('results/work/v14-review-QA'))
    parser.add_argument('--approve-layout',action='store_true');a=parser.parse_args()
    run(a.package,a.work,a.approve_layout)
