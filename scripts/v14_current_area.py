"""Apply the validated polygon-only area overlay to the closed search inventory."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path

from ls_satsearch.run import sha, write_json
from scripts import v14_mask_tiles as base
from scripts import v14_mask_overlay_repair as overlay

RECEIPT=base.OUTPUT/'post_outside_C_registration_20261120.json'


def registration():
    receipt=json.loads(RECEIPT.read_text());path=Path(receipt['registration'])
    if sha(path)!=receipt['registration_sha256']:
        raise ValueError('Post-source area registration changed')
    return path,base.load(path)


def setup():
    path,record=registration()
    # All geometry keys are already warmed. Revalidate and reclassify them
    # under this source inventory; never add old and new scalar areas.
    for i in range(record['shards']):base.vectorize(path,i)
    base.build_index(path)
    output=Path(record['output'])/'overlay_repair_registration.json'
    proof=dict(registration_sha256=sha(path),
        vector_index_sha256=sha(Path(record['output'])/'vector_index.json'),
        code_sha256=sha(Path(overlay.__file__)),driver_sha256=sha(Path(__file__)),
        scope='Same validated polygon-only projection: discard only zero-area lines/points, without snapping or mask changes. Current closed-search inventory; final scientific production/review freeze remains separate.')
    if output.exists() and json.loads(output.read_text())!=proof:
        raise ValueError('Preserve previous registered overlay')
    write_json(output,proof)
    print('CURRENT_AREA_OVERLAY_READY',path,flush=True)


def shard(path,index):
    overlay.REG=Path(path)
    _,root=overlay.context()
    proof=json.loads((root/'overlay_repair_registration.json').read_text())
    if proof['driver_sha256']!=sha(Path(__file__)):
        raise ValueError('Registered area driver changed')
    for number in range(index,720,24):
        if not (root/'tiles'/f'{number:03d}.json').exists() and not (root/'tiles_repaired'/f'{number:03d}.json').exists():
            overlay.tile(number)
    return index


def pack(index):
    if index not in range(3):raise ValueError('Expected three disjoint resource packs')
    path,_=registration()
    with ProcessPoolExecutor(max_workers=8) as pool:
        done=list(pool.map(shard,[str(path)]*8,range(index,24,3)))
    print('CURRENT_AREA_PACK_COMPLETE',index,done,flush=True)


def collect():
    path,record=registration();overlay.REG=path
    overlay.collect()
    output=Path(record['output'])/'overlay_repaired_summary.json'
    summary=json.loads(output.read_text())
    write_json(base.OUTPUT/'post_outside_C_union_acceptance.json',dict(
        job=os.environ['SLURM_JOB_ID'],registration=str(path),registration_sha256=sha(path),
        inventory_sha256=record['inventory_sha256'],summary=str(output),summary_sha256=sha(output),
        driver_sha256=sha(Path(__file__)),tiles=summary['tiles'],layers=summary['layers'],
        physical_gain_area_deg2=None,final_production_frozen=False,
        scope='All720disjoint equal-area tiles of the source-bound represented working masks. Qualification, census-boundary ambiguity and overlap retained. No scalar summation of overlapping masks, physical-gain footprint, continuous native-pixel claim, final candidate freeze or human release.'))


if __name__=='__main__':
    base.allocated()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('setup','pack','collect'));parser.add_argument('--index',type=int)
    a=parser.parse_args()
    {'setup':setup,'pack':lambda:pack(a.index),'collect':collect}[a.mode]()
