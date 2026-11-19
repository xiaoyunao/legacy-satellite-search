"""Repair area-only overlays of mixed polygon/line collections, preserving originals."""
import argparse
import json
import os
from pathlib import Path
from time import monotonic

import shapely
from shapely.geometry import Polygon, box

from ls_satsearch.run import sha, write_csv, write_json
from scripts import v14_mask_tiles as base

REG = base.OUTPUT/'tiled/3e675c854e361681/registration.json'


def polygons(geometry):
    """Lines and points have zero area; retain every polygon without snapping."""
    if geometry.geom_type in ('Polygon', 'MultiPolygon'):
        return geometry
    if hasattr(geometry, 'geoms'):
        return shapely.union_all([polygons(part) for part in geometry.geoms])
    return Polygon()


def context():
    base.allocated()
    registration = base.load(REG)
    root = Path(registration['output'])
    proof = json.loads((root/'overlay_repair_registration.json').read_text())
    if proof['registration_sha256'] != sha(REG) or proof['code_sha256'] != sha(Path(__file__)):
        raise ValueError('Area repair registration changed')
    if proof['vector_index_sha256'] != sha(root/'vector_index.json'):
        raise ValueError('Registered polygon index changed')
    return registration, root


def tile(number):
    registration, root = context()
    if not 0 <= number < 720:
        raise ValueError('Invalid tile')
    started = monotonic()
    vector_index = json.loads((root/'vector_index.json').read_text())
    cache = Path(registration['cache'])
    x, y = number % 36, number // 36
    bounds = (x*10, -1+y*.1, (x+1)*10, min(1., -1+(y+1)*.1))
    clip = box(*bounds)
    layers = {name:[[] for _ in range(4)] for name in
              ('all_ordinary_scanned', 'qualified_production')}
    for record in vector_index['records']:
        for label, bound in enumerate(record['bounds']):
            if bound is None or bound[2] <= bounds[0] or bound[0] >= bounds[2] or bound[3] <= bounds[1] or bound[1] >= bounds[3]:
                continue
            file = cache/f'{record["cache_key"]}-{label}.wkb'
            if sha(file) != record['geometry_sha256'][file.name]:
                raise ValueError('Source geometry changed')
            geometry = polygons(shapely.from_wkb(file.read_bytes()).intersection(clip))
            layers['all_ordinary_scanned'][label].append(geometry)
            if record['classification'] == 'qualified_discovery':
                layers['qualified_production'][label].append(geometry)
    rows = []
    max_area_difference = 0.
    for layer, parts in layers.items():
        raw = [shapely.union_all(items) for items in parts]
        unions = [polygons(g) for g in raw]
        max_area_difference = max(max_area_difference,
            max(abs(a.area-b.area)/base.RAD for a,b in zip(raw, unions)))
        total = shapely.union_all(unions)
        ambiguity = shapely.union_all([unions[i].intersection(unions[j]) for i in range(4) for j in range(i)])
        surveys = []
        for label, geometry in enumerate(unions):
            other = shapely.union_all([g for j,g in enumerate(unions) if j != label])
            surveys.append(dict(census_label=label, represented_label_union_deg2=geometry.area/base.RAD,
                unambiguous_deg2=geometry.difference(other).area/base.RAD))
        rows.append(dict(layer=layer, union_deg2=total.area/base.RAD,
            summed_record_pieces_deg2=sum(g.area for items in parts for g in items)/base.RAD,
            census_boundary_ambiguity_deg2=ambiguity.area/base.RAD, census=surveys))
    if max_area_difference > 1e-9:
        raise ValueError('Polygon-only projection changed a positive area')
    original = root/'tiles'/f'{number:03d}.json'
    comparison = None
    if original.exists():
        prior = json.loads(original.read_text())
        differences = [abs(a[key]-b[key]) for a,b in zip(prior['layers'],rows)
                       for key in ('union_deg2','summed_record_pieces_deg2','census_boundary_ambiguity_deg2')]
        comparison = max(differences)
        if comparison > 1e-9:
            raise ValueError('Area repair differs from original successful tile')
    output = root/'tiles_repaired'/f'{number:03d}.json'
    output.parent.mkdir(exist_ok=True)
    base.atomic_json(output, dict(job=os.environ['SLURM_JOB_ID'], tile=number,
        bounds_ra_sindec=bounds, registration_sha256=sha(REG),
        vector_index_sha256=sha(root/'vector_index.json'), layers=rows,
        repair_registration_sha256=sha(root/'overlay_repair_registration.json'),
        polygon_projection_max_area_delta_deg2=max_area_difference,
        original_successful_tile_max_delta_deg2=comparison, seconds=monotonic()-started))
    print('POLYGON_ONLY_AREA_TILE', number, flush=True)


def collect():
    registration, root = context()
    base.vector_proofs(registration, REG)
    totals, rows, sources = {}, [], {}
    for number in range(720):
        original = root/'tiles'/f'{number:03d}.json'
        source = original if original.exists() else root/'tiles_repaired'/f'{number:03d}.json'
        saved = json.loads(source.read_text())
        if saved['registration_sha256'] != sha(REG) or saved['tile'] != number or saved['vector_index_sha256'] != sha(root/'vector_index.json'):
            raise ValueError('Tile provenance differs')
        if source != original and saved['repair_registration_sha256'] != sha(root/'overlay_repair_registration.json'):
            raise ValueError('Tile repair provenance differs')
        sources[str(source)] = sha(source)
        for row in saved['layers']:
            rows.append(dict(tile=number, repaired=source != original, **{k:v for k,v in row.items() if k != 'census'}))
            total = totals.setdefault(row['layer'], dict(union_deg2=0., summed_record_pieces_deg2=0.,
                census_boundary_ambiguity_deg2=0., census=[dict(census_label=i,represented_label_union_deg2=0.,unambiguous_deg2=0.) for i in range(4)]))
            for key in ('union_deg2','summed_record_pieces_deg2','census_boundary_ambiguity_deg2'):
                total[key] += row[key]
            for i in range(4):
                for key in ('represented_label_union_deg2','unambiguous_deg2'):
                    total['census'][i][key] += row['census'][i][key]
    write_csv(root/'overlay_repaired_tile_areas.csv', rows)
    write_json(root/'overlay_repaired_summary.json', dict(job=os.environ['SLURM_JOB_ID'],tiles=720,
        layers=totals, input_sha256=sources, final_production_frozen=False,
        repair_registration_sha256=sha(root/'overlay_repair_registration.json'),
        scope='Original successful tiles preserved; missing tiles use polygon-only area overlays, without rounding or snapping. Original immutable working-mask snapshot, not final project or physical-gain area.'))
    print('REPAIRED_FULL_WORKING_MASK_UNION', totals, flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('pilot','shard','collect'));p.add_argument('--index',type=int)
    a=p.parse_args()
    if a.mode == 'pilot':
        for number in (1,26,73):tile(number)
    elif a.mode == 'collect':collect()
    else:
        _,root=context()
        if not 0 <= a.index < 24:raise ValueError('Invalid shard')
        for number in range(a.index,720,24):
            if not (root/'tiles'/f'{number:03d}.json').exists() and not (root/'tiles_repaired'/f'{number:03d}.json').exists():tile(number)
