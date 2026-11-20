"""Prepare the held scientific context PDF; never reveal it or fill grades.

Identity-bearing output must stay in final_private until actual phase-one
responses have been sealed. Use the bundled PDF runtime.
"""
import argparse
import hashlib
import json
from pathlib import Path
import textwrap

from PIL import Image
from reportlab.lib.pagesizes import landscape,A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build(key,output):
    if 'final_private' not in output.parts:raise ValueError('Keep held context private before response sealing')
    held=json.loads(key.read_text());inputs={str(key):sha(key)}
    output.mkdir(parents=True,exist_ok=False)
    pdf=output/'held_context.pdf';width,height=landscape(A4);margin=28
    doc=canvas.Canvas(str(pdf),pagesize=(width,height),pageCompression=1)
    doc.setTitle('Held scientific context');doc.setAuthor('');doc.setSubject('Withheld until actual anonymous responses are sealed')
    doc.setFont('Helvetica-Bold',20);doc.drawString(margin,height-50,'Held scientific context')
    doc.setFont('Helvetica',11)
    lines=['PRIVATE LAYOUT PILOT' if held.get('pilot') else 'Frozen review-unit identity and scientific evidence',
        'Do not reveal before actual phase-one user responses are sealed.',
        'This packet supplies source identities, C hypotheses and known/observing conditions.',
        'No human grades or new-system classifications have been inferred.',
        'C is follow-up of A discoveries; local TS is not a global-search significance.',
        'All retained source alternatives remain linked, including repeated source versions.',
        'Independent observations and physical PS1 completeness retain their separate limitations.']
    for i,line in enumerate(lines):doc.drawString(margin,height-95-24*i,line)
    doc.showPage();index=[]
    for unit in held['units']:
        alias=unit['anonymous_id'];first=doc.getPageNumber();doc.bookmarkPage(alias);doc.addOutlineEntry(alias,alias)
        doc.setFont('Helvetica-Bold',15);doc.drawString(margin,height-35,alias+' / source and C context')
        y=height-63
        def text(line):
            nonlocal y
            for part in textwrap.wrap(str(line),132,break_long_words=True) or ['']:
                if y<38:
                    doc.showPage();doc.setFont('Helvetica-Bold',13);doc.drawString(margin,height-30,alias+' / context continued');y=height-55
                doc.setFont('Helvetica',9);doc.drawString(margin,y,part);y-=13
        text('Original exposed cases: '+(', '.join(unit.get('old_ids',[])) or 'none'))
        text('Control: '+str(unit.get('control') or 'none')+'; prior exposure: '+str(unit.get('prior_exposure',False)))
        if unit.get('selection'):
            text('Allocation: '+str(unit['selection']['selection_reason'])+'; inclusion probability: '+str(unit['selection']['inclusion_probability']))
        for source in unit.get('production_record_ids',[]):text('Qualified source record: '+source)
        alternatives=[]
        for j,alternative in enumerate(unit['alternatives'],1):
            origins=alternative['origins'];path=Path(origins[0]['context_manifest'])
            if sha(path)!=origins[0]['context_manifest_sha256']:raise ValueError('Held saved-mode context changed')
            context=json.loads(path.read_text());mode=context['mode'];inputs[str(path)]=sha(path)
            if not context['membership_integrity']['verified']:raise ValueError('Saved member/likelihood proof failed')
            text(f"Retained view {j:03d}: RA={mode['fit_ra_deg']}; Dec={mode['fit_dec_deg']}; DM={mode['fit_dm']}; rh={mode['fit_rh_arcmin']} arcmin")
            text(f"C TS={mode['ts']}; without top3={mode['C_refit_TS_without_top3']}; effective members={mode.get('effective_members','unavailable')}; evidence L0")
            text('Original mode/source references: '+', '.join(o['context_manifest'] for o in origins))
            alternatives.append((j,path,context))
        doc.showPage()
        for j,path,context in alternatives:
            for name in ('context.png','conditions.png','images.png'):
                image_path=path.parent/name
                if sha(image_path)!=context['outputs'][name]:raise ValueError('Held raster changed')
                inputs[str(image_path)]=sha(image_path)
                doc.setFont('Helvetica-Bold',12);doc.drawString(margin,height-28,f'{alias} / retained view {j:03d} / '+name.replace('.png',''))
                with Image.open(image_path) as im:
                    im.verify()
                with Image.open(image_path) as im:
                    rgb=im.convert('RGB');iw,ih=rgb.size;scale=min((width-2*margin)/iw,(height-80)/ih)
                    doc.drawImage(ImageReader(rgb),(width-iw*scale)/2,height-45-ih*scale,width=iw*scale,height=ih*scale)
                doc.setFont('Helvetica',8);doc.drawString(margin,18,'Held context. No independent confirmation or human classification is implied.');doc.drawRightString(width-margin,18,str(doc.getPageNumber()))
                doc.showPage()
        index.append(dict(anonymous_id=alias,first_page=first,last_page=doc.getPageNumber()-1,views=len(alternatives)))
    doc.save()
    for name,digest in inputs.items():
        if sha(Path(name))!=digest:raise ValueError('Held input changed during assembly')
    receipt=dict(inputs=inputs,code_sha256=sha(Path(__file__)),pdf_sha256=sha(pdf),page_index=index,
        units=len(held['units']),pages=doc.getPageNumber()-1,pilot=bool(held.get('pilot')),
        identity_revealed=False,human_grades_filled=False,full_page_QA_pending=True,
        scope='Prepared private phase-two context only. No response seal, identity reveal, final release or candidate classification.')
    (output/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(dict(units=receipt['units'],pages=receipt['pages'],held_private=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--key',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();build(args.key,args.output)
