"""Build separate priority and identity-blind PDF packets from real diagnostics.

Use the bundled PDF Python runtime, or install the project's review extra.
This script reads no survey FITS or source/member tables.
"""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
from importlib.metadata import version
import json
from pathlib import Path
import zipfile

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT=Path('results/v14/shortlist')
W,H=landscape(A4)
MARGIN=28


def read(path):
    with path.open() as stream:return list(csv.DictReader(stream))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def validate_registration():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for name,checksum in manifest['packet_hashes'].items():
        if digest(Path(name))!=checksum:raise ValueError('Frozen case/mode packet changed: '+name)
    if digest(Path('configs/v14/shortlist_plan.yaml'))!=manifest['plan_sha256']:
        raise ValueError('Frozen shortlist policy changed')


def select_packet(case):
    required=read(ROOT/f'input_modes_{case["cohort"]}.csv')
    required={int(float(r['peak_rank'])) for r in required if r['group_id']==case['source_group_id']}
    for source in ('cases','cached_cases'):
        folder=ROOT/source/case['case_id'];path=folder/'review_modes.csv'
        if not path.is_file():continue
        modes=read(path)
        present={int(float(m['rank'])) for m in modes}
        if present==required and all(m['fit_status']=='complete' for m in modes):
            return folder,modes
    return None,[]


def ready(case):
    folder,modes=select_packet(case)
    evidence=ROOT/'evidence'/case['case_id']
    reasons=[]
    if not modes:reasons.append('Retained C modes pending/incomplete')
    else:
        for m in modes:
            rank=int(float(m['rank']))
            for suffix in ('','-environment','-images'):
                path=folder/f'seed-{rank}{suffix}.png'
                if not path.is_file():
                    reasons.append('Full-mode diagnostic PNG missing');break
                try:
                    with Image.open(path) as picture:picture.verify()
                except (OSError,ValueError,SyntaxError):reasons.append('Full-mode diagnostic PNG is corrupt')
        for name in ('evidence.png','images.png','provenance.json'):
            if not (evidence/name).is_file():reasons.append(f'Observed anonymous evidence pending: {name}')
        if (evidence/'provenance.json').is_file():
            p=json.loads((evidence/'provenance.json').read_text())
            if p['mode_table_sha256']!=digest(folder/'review_modes.csv'):
                reasons.append('Supplementary evidence does not match C table')
        best=max(modes,key=lambda m:float(m['ts']))
        context=ROOT/'postfit_context.csv'
        positions=[r for r in read(context) if r['case_id']==case['case_id']] if context.is_file() else []
        if not any(r['position_type']=='discovery' for r in positions):reasons.append('Discovery-centre context pending')
        if not any(r['position_type']=='C_refit' and int(float(r['mode_rank']))==int(float(best['rank']))
                   for r in positions):reasons.append('Best fitted-centre context pending')
        integrity=Path('results/v14/human_review/membership_integrity.json')
        proof=json.loads(integrity.read_text()) if integrity.is_file() else {}
        if not (proof.get('all_registered_positions') and
                proof.get('shortlist_manifest_sha256')==digest(ROOT/'manifest.json') and
                proof.get('csv_sha256')==digest(integrity.with_suffix('.csv')) and
                proof.get('table_hashes',{}).get(case['case_id'])==digest(folder/'review_modes.csv')):
            reasons.append('All-mode saved membership integrity verification pending')
        elif (evidence/'provenance.json').is_file():
            verified=read(integrity.with_suffix('.csv'))
            expected=next((r for r in verified if r['case_id']==case['case_id'] and
                           int(r['seed_rank'])==int(float(best['rank']))),{})
            if p.get('membership_sha256')!=expected.get('membership_sha256'):
                reasons.append('Observed panel membership differs from verified snapshot')
    return folder,modes,list(dict.fromkeys(reasons))


def new_page(pdf,title,subtitle=''):
    pdf.setFillColor(colors.HexColor('#20384a'));pdf.setFont('Helvetica-Bold',16)
    pdf.drawString(MARGIN,H-30,title)
    pdf.setFont('Helvetica',9);pdf.setFillColor(colors.HexColor('#465761'))
    pdf.drawString(MARGIN,H-47,subtitle)


def footer(pdf,label):
    pdf.setFillColor(colors.HexColor('#586976'));pdf.setFont('Helvetica',8)
    pdf.drawString(MARGIN,14,label)
    pdf.drawRightString(W-MARGIN,14,str(pdf.getPageNumber()))
    pdf.showPage()


def image(pdf,path,box,crop_top=0,crop_box=None):
    with Image.open(path) as im:
        if crop_top:im=im.crop((0,int(im.height*crop_top),im.width,im.height))
        if crop_box:im=im.crop(tuple(int(v*s) for v,s in zip(crop_box,(im.width,im.height,im.width,im.height))))
        buf=io.BytesIO();im.save(buf,format='PNG')
        iw,ih=im.size
    x,y,w,h=box;scale=min(w/iw,h/ih)
    pdf.drawImage(ImageReader(buf),x+(w-iw*scale)/2,y+(h-ih*scale)/2,
                  width=iw*scale,height=ih*scale,mask='auto')


def lines(pdf,rows,x,y,size=10,leading=18):
    pdf.setFillColor(colors.HexColor('#20384a'));pdf.setFont('Helvetica',size)
    for row in rows:
        pdf.drawString(x,y,row);y-=leading
    return y


def response_template(path,cases,blind):
    # Never overwrite a human's recorded responses when regenerating a packet.
    if path.exists():return
    columns=['case_id','reviewer','reviewed_utc','morphology','CMD','spatial',
             'technical_concern','confidence','comments']
    if not blind:columns.insert(7,'decision')
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,columns,lineterminator='\n');writer.writeheader()
        writer.writerows(dict(case_id=c['case_id']) for c in cases)


def build_group(cases,output,blind,require_complete):
    packets={c['case_id']:ready(c) for c in cases}
    missing={key:value[2] for key,value in packets.items() if value[2]}
    if missing and require_complete:
        raise ValueError(f'Review packet not complete: {len(missing)}/{len(cases)} positions pending')
    filename=('blind_phase1' if blind else 'priority_review')+('_INCOMPLETE' if missing else '')+'.pdf'
    target=output/filename
    pdf=canvas.Canvas(str(target),pagesize=(W,H),pageCompression=1)
    pdf.setTitle('Anonymous morphology CMD spatial review' if blind else 'Priority candidate science review')
    pdf.setAuthor('Legacy Satellite Search')
    title='Anonymous morphology / CMD / spatial review' if blind else 'Priority candidate review'
    new_page(pdf,title,('INCOMPLETE - not released for human review' if missing else 'Complete first frozen review cohort'))
    text=[f'Registered positions: {len(cases)}. Complete evidence packets: {len(cases)-len(missing)}.',
          'Use the separate blank response CSV; no scientific grades have been filled.',
          'All entries stay in the registered denominator, including failed or rejected cases.',
          'Marginal photometric errors share g between colour and magnitude; they are correlated.',
          'The background CMD has equal geometric area; inspect exposure masks.',
          'C membership is model dependent; repeated methods are not independent confirmation.']
    if blind:
        text += ['','Phase 1 hides coordinates, field identity, survey region, discovery ranks/scores,',
                 'C summary scores, known objects, source-processing environment labels and prior decisions.',
                 'Seal the morphology/CMD/spatial responses before opening any reveal key.',
                 'The rendered evidence retains only anonymous B IDs and relative axes.',
                 'The audit is exploratory: spatial exclusions make inclusion nonuniform.']
    else:
        text += ['','Record one decision: follow-up / suspected contamination / known environment / insufficient evidence.',
                 'Each object has measured evidence, native gr cutouts, all retained C solutions and context.',
                 'Existing automated/assistant triage is separate from your response form.']
    lines(pdf,text,MARGIN,H-90);footer(pdf,'Frozen first R14 production review | L0 unless independently assessed')
    source_hashes={};page_index=[]
    context=read(ROOT/'postfit_context.csv') if not blind else []
    for c in cases:
        cid=c['case_id'];folder,modes,reasons=packets[cid];first=pdf.getPageNumber()
        subtitle=''
        if not blind and modes:
            centre=max(modes,key=lambda m:float(m['ts']))
            subtitle=f'Evidence centred on C fit: ICRS {float(centre["fit_ra_deg"]):.5f}, {float(centre["fit_dec_deg"]):+.5f}'
        new_page(pdf,cid+' | observed population and spatial evidence',subtitle)
        if reasons:
            lines(pdf,['NOT READY - no substitute or simulated result is inserted.',*reasons],MARGIN,H-90)
            footer(pdf,cid+' | pending; do not grade absent evidence')
        else:
            supplement=ROOT/'evidence'/cid
            for mode in modes:
                mode_rank=int(float(mode['rank']))
                for suffix in ('','-environment','-images'):
                    path=folder/f'seed-{mode_rank}{suffix}.png'
                    source_hashes[str(path)]=digest(path)
            for name in ('evidence.png','images.png'):
                if name!='evidence.png':new_page(pdf,cid+' | native g/r pixels and strongest contributors')
                source=supplement/name;source_hashes[str(source)]=digest(source)
                status=json.loads((supplement/'provenance.json').read_text())
                if name=='images.png' and status.get('image_expected_member_stamps')==0:
                    # Only the two measured centre images exist; do not retain
                    # six blank contributor slots or invent replacement stars.
                    width=(W-2*MARGIN)/2
                    image(pdf,source,(MARGIN,65,width,H-145),crop_box=(0,.05,.28,.52))
                    image(pdf,source,(MARGIN+width,65,width,H-145),crop_box=(0,.53,.28,1))
                    lines(pdf,['No positive-probability C contributors in this fitted mode; only centre images exist.'],
                          MARGIN,48,size=10)
                else:image(pdf,source,(MARGIN,35,W-2*MARGIN,H-92))
                footer(pdf,cid+' | measured LS photometry and images; no independent confirmation implied')
            if not blind:
                best=max(modes,key=lambda m:float(m['ts']));rank=int(float(best['rank']))
                new_page(pdf,cid+' | distance response, radial distribution and exposure mask',
                         f'Discovery ICRS {float(c["ra_deg"]):.6f}, {float(c["dec_deg"]):+.6f}; {c["cohort"]}; plots centred on C fit')
                path=folder/f'seed-{rank}.png';source_hashes[str(path)]=digest(path)
                image(pdf,path,(MARGIN,35,W-2*MARGIN,H-92))
                footer(pdf,cid+' | raw discovery scores are not comparable between survey regions')
                new_page(pdf,cid+' | observing conditions',
                         'Depth, seeing and extinction at the fitted centre; inspect discontinuities and image artifacts.')
                path=folder/f'seed-{rank}-environment.png';source_hashes[str(path)]=digest(path)
                image(pdf,path,(MARGIN,35,W-2*MARGIN,H-92),crop_top=.07)
                footer(pdf,cid+' | environmental annotations are context, not physical membership')
                for start in range(0,len(modes),20):
                    chunk=modes[start:start+20]
                    new_page(pdf,cid+' | retained C solutions and known context',
                             'All retained seeds; C TS and deletion TS are local statistics, not global significance.')
                    x=[MARGIN,78,132,186,248,312,376,440,504,596,688]
                    headers=['seed','seed DM','fit DM','r_h (arcmin)','C TS','minus top 1','minus top 3','N_eff','C RA (deg)','C Dec (deg)','image pending']
                    pdf.setFont('Helvetica-Bold',8)
                    for xx,h in zip(x,headers):pdf.drawString(xx,H-78,h)
                    y=H-97;pdf.setFont('Helvetica',8)
                    for m in chunk:
                        vals=[m.get(k,'') for k in ('rank','seed_dm','fit_dm','fit_rh_arcmin','ts',
                              'C_refit_TS_without_top1','C_refit_TS_without_top3','effective_members',
                              'fit_ra_deg','fit_dec_deg','image_pending')]
                        for j,(xx,value) in enumerate(zip(x,vals)):
                            try:value=(str(int(float(value))) if j==0 else
                                       f'{float(value):.5f}' if j in (8,9) else f'{float(value):.3f}')
                            except (ValueError,TypeError):pass
                            pdf.drawString(xx,y,str(value))
                        y-=15
                    locations=[r for r in context if r['case_id']==cid and (r['position_type']=='discovery' or str(r['mode_rank'])==str(rank))]
                    note=[]
                    for r in locations:
                        note += [f"{r['position_type']}: nearest census {r['census_system'] or 'none'}; separation {r['census_arcmin'] or 'NA'} arcmin",
                                 f"SGA {r['nearest_sga'] or 'none'}; ellipse multiple {r['ellipse_radius_multiple'] or 'NA'}"]
                    note += ['Context is not physical association or classification. Keep all retained modes.',
                             'Independent imaging: consult archive metadata; overlap does not demonstrate independence.']
                    lines(pdf,note,MARGIN,min(y-20,180),size=9,leading=15)
                    footer(pdf,cid+' | record your own science decision in the response CSV')
            source_hashes[str(folder/'review_modes.csv')]=digest(folder/'review_modes.csv')
        page_index.append(dict(case_id=cid,first_page=first,last_page=pdf.getPageNumber()-1,ready=not reasons))
    pdf.save()
    return dict(file=str(target),sha256=digest(target),positions=len(cases),complete=len(cases)-len(missing),
        materials_complete=not missing,missing=missing,pages=pdf.getPageNumber()-1,
                page_index=page_index,source_hashes=source_hashes)


def run(output,require_complete=False):
    output.mkdir(parents=True,exist_ok=True)
    validate_registration()
    previous=output/'package_manifest.json'
    if previous.is_file():
        saved=json.loads(previous.read_text())
        if saved.get('materials_complete'):
            for item in saved['packages'].values():
                if digest(Path(item['file']))!=item['sha256']:raise ValueError('Released PDF changed; use a new output version')
            if 'anonymous_zip' in saved and digest(Path(saved['anonymous_zip']['file']))!=saved['anonymous_zip']['sha256']:
                raise ValueError('Released anonymous ZIP changed')
            print('Existing assembled package verified; user forms and artifact hashes preserved')
            return
    cases=read(ROOT/'cases.csv')
    if len(cases)!=75 or sum(c['queue']=='priority' for c in cases)!=40:
        raise ValueError('Frozen denominator differs from 40 priority plus 35 audit positions')
    results={}
    for blind,key in ((False,'priority'),(True,'blind_phase1')):
        subset=[c for c in cases if (c['queue']!='priority')==blind]
        results[key]=build_group(subset,output,blind,require_complete)
        response_template(output/f'{key}_responses_blank.csv',subset,blind)
    manifest=dict(
        utc=datetime.now(timezone.utc).isoformat(),shortlist_manifest_sha256=digest(ROOT/'manifest.json'),
        compiler_sha256=digest(Path(__file__)),
        membership_integrity_sha256=digest(Path('results/v14/human_review/membership_integrity.json')) if require_complete else None,
        versions={name:version(name) for name in ('reportlab','pypdf','pillow')},
        materials_complete=all(r['materials_complete'] for r in results.values()),
        render_QA_complete=False,ready_for_human_review=False,
        packages=results,scope='Prepared evidence and blank forms only. No human grades or completeness inference. Anonymous PDF must be reviewed before opening reveal files.')
    if manifest['materials_complete']:
        target=output/'anonymous_phase1_only.zip'
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(results['blind_phase1']['file'],'blind_phase1.pdf')
            archive.write(output/'blind_phase1_responses_blank.csv','responses_blank.csv')
            archive.writestr('READ_FIRST.txt','Review B001-B035 using these panels only. Save morphology/CMD/spatial responses before opening any identity, score, environment or association key. Blank response fields are yours to fill. The sampling design is exploratory, not a calibrated completeness experiment.\n')
            for case in cases:
                if case['queue']=='priority':continue
                for name in ('evidence.png','images.png'):
                    with Image.open(ROOT/'evidence'/case['case_id']/name) as original:
                        # Strip metadata without changing the diagnostic pixels.
                        im=Image.frombytes('RGB',original.size,original.convert('RGB').tobytes())
                        buf=io.BytesIO();im.save(buf,format='PNG')
                        archive.writestr(f'panels/{case["case_id"]}-{name}',buf.getvalue())
        manifest['anonymous_zip']=dict(file=str(target),sha256=digest(target),
            scope='Standalone phase-1 PDF, opaque panel images and blank responses only. No identity keys or provenance filenames.')
    (output/'package_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print({key:{k:r[k] for k in ('positions','complete','pages','materials_complete')} for key,r in results.items()})


def preparation_status(output):
    output.mkdir(parents=True,exist_ok=True)
    validate_registration()
    cases=read(ROOT/'cases.csv');rows=[]
    for case in cases:
        _,modes,reasons=ready(case)
        rows.append(dict(case_id=case['case_id'],queue=case['queue'],C_modes_complete=len(modes),
                         measured_review_ready=not reasons,pending=' | '.join(reasons)))
    with (output/'preparation_status.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    released=output/'package_manifest.json'
    state=dict(utc=datetime.now(timezone.utc).isoformat(),registered=len(rows),
        retained_C_packets_complete=sum(r['C_modes_complete']>0 for r in rows),
        observed_supplement_packets_present=sum(all((ROOT/'evidence'/r['case_id']/name).is_file()
                                                   for name in ('evidence.png','images.png','provenance.json')) for r in rows),
        measured_review_ready=sum(r['measured_review_ready'] for r in rows),
        materials_complete=all(r['measured_review_ready'] for r in rows),
        ready_for_human_review=(json.loads(released.read_text()).get('ready_for_human_review',False) if released.is_file() else False),
        scope='Preparation only. Full PDFs/anonymous ZIP are released only when both cohorts pass. User grades remain empty.')
    (output/'preparation_status.json').write_text(json.dumps(state,indent=2)+'\n');print(state)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--allow-incomplete',action='store_true',help='Internal layout QA only, not a review release')
    parser.add_argument('--status-only',action='store_true',help='Record actual preparation readiness without releasing PDFs')
    args=parser.parse_args()
    output=args.output or Path('results/work/v14-human-review' if args.allow_incomplete else 'results/v14/human_review')
    if args.status_only:preparation_status(output)
    else:run(output,not args.allow_incomplete)
