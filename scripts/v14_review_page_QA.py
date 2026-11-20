"""Render every final review page locally; keep identity-bearing QA private.

Uses the bundled PDFium runtime. Layout/render QA never fills human grades.
Contact sheets are a visual overview, not a substitute for source-pixel checks.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageStat


def digest(path):
    with path.open('rb') as stream:
        return __import__('hashlib').file_digest(stream, 'sha256').hexdigest()


def run(source, output, contacts):
    if 'final_private' not in output.parts:
        raise ValueError('Keep pre-release page QA private')
    output.mkdir(parents=True, exist_ok=False)
    original=digest(source); document=pdfium.PdfDocument(source)
    records=[]; sheets=[]; sheet=None; tile_width=300; tile_height=238
    for index in range(len(document)):
        page=document[index];width,height=page.get_size();text=page.get_textpage()
        outside=[]
        for char in range(text.count_chars()):
            left,bottom,right,top=text.get_charbox(char)
            if min(left,bottom)<-1 or right>width+1 or top>height+1:
                outside.append(char)
        if outside:raise ValueError(f'Page {index+1} has text outside page bounds')
        for obj in page.get_objects():
            left,bottom,right,top=obj.get_bounds()
            if min(left,bottom)<-1 or right>width+1 or top>height+1:
                raise ValueError(f'Page {index+1} has an object outside page bounds')
        bitmap=page.render(scale=1);image=bitmap.to_pil().convert('RGB')
        if min(ImageStat.Stat(image).stddev)<1:
            raise ValueError(f'Unexpected blank rendered page {index+1}')
        records.append(dict(page=index+1,size=list(image.size),
                            rendered_pixel_sha256=sha256(image.tobytes()).hexdigest(),
                            text_and_objects_inside_page=True,nonblank=True))
        if contacts:
            slot=index%40
            if slot==0:sheet=Image.new('RGB',(5*tile_width,8*tile_height),'#e6e6e6')
            thumb=image.copy();thumb.thumbnail((tile_width-8,tile_height-22))
            x=(slot%5)*tile_width;y=(slot//5)*tile_height
            sheet.paste(thumb,(x+(tile_width-thumb.width)//2,y+20))
            ImageDraw.Draw(sheet).text((x+8,y+4),f'Page {index+1}',fill='black')
            if slot==39 or index==len(document)-1:
                name=f'contact_{len(sheets)+1:03d}.png';sheet.save(output/name)
                sheets.append(dict(path=name,sha256=digest(output/name),
                                   first_page=index-slot+1,last_page=index+1))
        image.close();bitmap.close();text.close();page.close()
        if (index+1)%100==0:print(dict(rendered_pages=index+1),flush=True)
    document.close()
    if digest(source)!=original:raise ValueError('PDF changed during page QA')
    receipt=dict(pdf_sha256=original,code_sha256=digest(Path(__file__)),pages=len(records),
                 every_page_rendered=True,every_page_text_and_object_bounds_checked=True,
                 rendered_pages=records,contact_sheets=sheets,
                 contact_sheets_visually_inspected=False,final_ready_for_human_review=False,
                 scope='Independent all-page rendering/nonblank/bounds audit. Every source pixel and package privacy are separate checks. No scientific or human grade inferred.')
    (output/'render_QA.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(dict(pages=len(records),contact_sheets=len(sheets),all_pages_rendered=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--contacts',action='store_true');args=parser.parse_args()
    run(args.pdf,args.output,args.contacts)
