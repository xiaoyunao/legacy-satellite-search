"""Finalize an already verified anonymous package; never reveal its held key."""
import argparse
from hashlib import file_digest
import json
import os
from pathlib import Path
import zipfile


def digest(path):
    with path.open('rb') as stream:return file_digest(stream,'sha256').hexdigest()


def load(path):return json.loads(path.read_text())


def release(package,assembly,render_qa,visual_qa,held,held_render_qa):
    manifest_path=package/'package_manifest.json';manifest=load(manifest_path)
    if manifest['pilot'] or manifest['final_ready_for_human_review']:
        raise ValueError('Require a nonpilot package that has not already been released')
    registration=load(assembly/'registration.json');structure=load(package/'structural_QA.json')
    render=load(render_qa);visual=load(visual_qa);held_proof=load(held/'structural_QA.json')
    held_render=load(held_render_qa)
    if (registration['anonymous_units']!=manifest['units'] or registration['original75_retained']!=75
            or registration['weak_controls']!=2 or registration['human_grades_filled']):
        raise ValueError('Final unit/control/original-case gate failed')
    if (structure['package_manifest_sha256']!=digest(manifest_path)
            or structure['plan_sha256']!=digest(assembly/'anonymous_plan.json')):
        raise ValueError('Full pixel/ZIP/form check belongs to another package')
    for flag in ('every_evidence_page_pixel_roundtrip_verified','neutral_evidence_page_text_verified',
                 'standalone_zip_verified','blank_forms_verified'):
        if structure.get(flag) is not True:raise ValueError('Missing full integrity check: '+flag)
    for qa,pdf,pages in ((render,package/'anonymous_review.pdf',manifest['pages']),
                         (held_render,held/'held_context.pdf',held_proof['pages'])):
        if (qa['pdf_sha256']!=digest(pdf) or qa['pages']!=pages
                or not qa['every_page_rendered'] or not qa['every_page_text_and_object_bounds_checked']):
            raise ValueError('Every-page render/layout check required')
    if (held_proof['pdf_sha256']!=digest(held/'held_context.pdf')
            or not held_proof['every_held_image_pixel_roundtrip_verified']
            or held_proof['key_sha256']!=digest(assembly/'held_context_key.json')):
        raise ValueError('Held all-mode context integrity gate failed')
    if (visual['render_QA_sha256']!=digest(render_qa)
            or visual['contact_sheets_inspected']!=render['contact_sheets']
            or not visual['all_contact_sheets_inspected']
            or not visual['neutral_renderer_annotation_audit_passed']):
        raise ValueError('Actual full anonymous overview/annotation inspection required')
    for name,checksum in manifest['artifacts'].items():
        if Path(name).name!=name or digest(package/name)!=checksum:
            raise ValueError('Released material changed')
    if digest(package/'anonymous_review.zip')!=manifest['zip_sha256']:
        raise ValueError('Pre-QA archive changed')
    qa_paths=[package/'structural_QA.json',render_qa,visual_qa,held/'structural_QA.json',held_render_qa]
    # Preserve the draft receipt. Only readiness metadata changes; PDF/forms/index stay byte-identical.
    (package/'package_manifest.preQA.json').write_bytes(manifest_path.read_bytes())
    with zipfile.ZipFile(package/'anonymous_review.zip') as archive:
        inner=json.loads(archive.read('manifest.json'))
    inner.update(final_ready_for_human_review=True,
                 scope='Frozen anonymous evidence and blank response form. Identity/context key withheld until actual user responses are sealed.')
    temporary=package/'anonymous_review.finalizing.zip'
    with zipfile.ZipFile(temporary,'x',zipfile.ZIP_DEFLATED) as archive:
        for name in manifest['artifacts']:archive.write(package/name,name)
        archive.writestr('manifest.json',json.dumps(inner,indent=2)+'\n')
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() or set(archive.namelist())!=set(manifest['artifacts'])|{'manifest.json'}:
            raise ValueError('Final anonymous ZIP integrity failed')
        for name,checksum in manifest['artifacts'].items():
            from hashlib import sha256
            if sha256(archive.read(name)).hexdigest()!=checksum:raise ValueError('ZIP content differs')
        if not json.loads(archive.read('manifest.json'))['final_ready_for_human_review']:
            raise ValueError('Inner final readiness differs')
    os.replace(temporary,package/'anonymous_review.zip')
    manifest.update(final_ready_for_human_review=True,zip_sha256=digest(package/'anonymous_review.zip'),
                    QA_proofs_sha256={str(p):digest(p) for p in qa_paths},
                    scope=inner['scope'])
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(dict(units=manifest['units'],pages=manifest['pages'],package_QA_passed=True,
               durable_archive_and_delivery_status_still_required=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('package','assembly','render-qa','visual-qa','held','held-render-qa'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();release(a.package,a.assembly,a.render_qa,a.visual_qa,a.held,a.held_render_qa)
