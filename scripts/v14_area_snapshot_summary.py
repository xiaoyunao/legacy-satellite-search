"""Audit completed tiled-area aggregates without copying mask pixels or geometries."""
import argparse
from collections import defaultdict
from pathlib import Path

from ls_satsearch.run import read_csv,sha,write_csv,write_json
import json


def run(root):
    summary=root/'overlay_repaired_summary.json';table=root/'overlay_repaired_tile_areas.csv';registration=root/'overlay_repair_registration.json'
    d=json.loads(summary.read_text());inputs={str(p):sha(p) for p in (summary,table,registration)}
    if d['repair_registration_sha256']!=sha(registration):raise ValueError('Area repair registration changed')
    rows=read_csv(table);groups=defaultdict(list)
    for r in rows:groups[r['layer']].append(r)
    if len(d['input_sha256'])!=720 or d['tiles']!=720:raise ValueError('Missing tile provenance')
    output=[]
    for key,layer in d['layers'].items():
        rs=groups[key]
        if len(rs)!=720 or len({r['tile'] for r in rs})!=720:raise ValueError('Tile partition incomplete or duplicated')
        for metric in ('union_deg2','summed_record_pieces_deg2','census_boundary_ambiguity_deg2'):
            if abs(sum(float(r[metric]) for r in rs)-layer[metric])>1e-7:raise ValueError('Tile aggregate mismatch: '+metric)
        if layer['union_deg2']>layer['summed_record_pieces_deg2']+1e-7:raise ValueError('Union exceeds input pieces')
        if abs(sum(r['unambiguous_deg2'] for r in layer['census'])+layer['census_boundary_ambiguity_deg2']-layer['union_deg2'])>1e-7:raise ValueError('Unambiguous census labels do not partition union')
        output.append(dict(layer=key,represented_working_mask_union_deg2=layer['union_deg2'],summed_record_pieces_deg2=layer['summed_record_pieces_deg2'],duplicate_overlap_removed_deg2=layer['summed_record_pieces_deg2']-layer['union_deg2'],census_boundary_ambiguity_deg2=layer['census_boundary_ambiguity_deg2'],tiles=720,final_production_frozen=False))
    if d['layers']['qualified_production']['union_deg2']>d['layers']['all_ordinary_scanned']['union_deg2']+1e-7:raise ValueError('Qualified subset exceeds all ordinary scans')
    write_csv(root/'area_snapshot_summary.csv',output)
    write_json(root/'overlay_repaired_QA.json',dict(inputs=inputs,code_sha256=sha(Path(__file__)),tile_partition_and_numerical_sums_passed=True,census_unambiguous_plus_ambiguity_balance_passed=True,original_tiles=sum(r['repaired']=='False' for r in groups['qualified_production']),repaired_tiles=sum(r['repaired']=='True' for r in groups['qualified_production']),final_production_frozen=False,scope='Accepted immutable6269 ordinary completed-mask snapshot, including zero-peak fields. Qualified area is a source-clock-qualified subset; later completed masks awaiting matching source ledgers remain unqualified. Exact union of represented WCS working cells is not a continuous native-pixel area, physical completeness, measured-gain area or final full-project footprint. Labelled unions can overlap inside the recorded census-boundary ambiguity; do not sum them as an exclusive partition.'))
    print(output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);run(**vars(p.parse_args()))
