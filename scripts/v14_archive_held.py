"""Compress verified held context for durable copies; never include it in phase one."""
import argparse
from hashlib import file_digest
import json
from pathlib import Path
import zipfile


def digest(path):
    with path.open('rb') as stream:return file_digest(stream,'sha256').hexdigest()


def archive(package,key=Path('results/v14/human_review/final_private/final_assembly/held_context_key.json')):
    if 'final_private' not in package.parts:raise ValueError('Held archive must remain private')
    manifest=json.loads((package/'manifest.json').read_text())
    qa=json.loads((package/'structural_QA.json').read_text())
    pdf=package/'held_context.pdf';checksum=digest(pdf)
    if (checksum!=manifest['pdf_sha256'] or checksum!=qa['pdf_sha256']
            or not qa['every_held_image_pixel_roundtrip_verified']):
        raise ValueError('Complete held source-pixel verification required')
    names=['held_context.pdf','manifest.json','structural_QA.json']
    artifacts={name:package/name for name in names}
    environment=package.parent/'held_environment'
    env=json.loads((environment/'manifest.json').read_text())
    render=json.loads((environment/'render_QA.json').read_text())
    env_pdf=environment/'held_environments.pdf'
    if (digest(env_pdf)!=env['pdf_sha256'] or digest(env_pdf)!=render['pdf_sha256']
            or env['inputs'].get(str(key))!=qa['key_sha256']
            or digest(key)!=qa['key_sha256']
            or not env['every_rendered_annotation_text_verified']
            or not render['every_page_rendered'] or not render['every_page_text_and_object_bounds_checked']):
        raise ValueError('Held frozen environment appendix and every-page QA required')
    for name in ('held_environments.pdf','manifest.json','render_QA.json'):
        artifacts['held_environment/'+name]=environment/name
    target=package.parent/'held_context.zip'
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as output:
        for name,path in artifacts.items():output.write(path,name)
    with zipfile.ZipFile(target) as output:
        if output.namelist()!=list(artifacts) or output.testzip():raise ValueError('Held archive integrity failed')
    receipt=dict(archive_sha256=digest(target),archive_bytes=target.stat().st_size,
        artifacts={name:digest(path) for name,path in artifacts.items()},
        code_sha256=digest(Path(__file__)),private=True,identity_revealed=False,
        scope='Durable-copy compression of verified private scientific context. Excluded from anonymous ZIP; no grades or response seal.')
    (package.parent/'held_archive.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(dict(held_archive_bytes=receipt['archive_bytes'],private=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--key',type=Path)
    args=parser.parse_args()
    if args.key:
        archive(args.package,args.key)
    else:
        archive(args.package)
