"""Cache original working-mask polygons and union disjoint equal-area tiles."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from time import monotonic

import numpy as np
import shapely
from shapely.geometry import box

from ls_satsearch.fields import Census
from ls_satsearch.data import Field
from ls_satsearch.expansion import field_bounds
from ls_satsearch.run import sha, write_csv, write_json
from scripts.v14_mask_union import RAD, extract

OUTPUT = Path('results/v14/production_integration/masks')
METHODS = (Path(__file__), Path('scripts/v14_mask_union.py'))


def encoded(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def allocated():
    if not os.getenv('SLURM_JOB_ID'):
        raise ValueError('Run geometry calculations on an allocated CPU node')


def load(path):
    record = json.loads(path.read_text())
    for name, checksum in record['method_sha256'].items():
        if sha(Path(name)) != checksum:
            raise ValueError('Registered geometry method changed: ' + name)
    if sha(Path(record['inventory'])) != record['inventory_sha256']:
        raise ValueError('Registered immutable mask inventory changed')
    return record


def prepare(shards, source, window=None):
    """Metadata registration only; does not open or process survey pixels."""
    if shards < 1:
        raise ValueError('Positive shard count required')
    raw = source.read_bytes()
    key = hashlib.sha256(raw).hexdigest()
    snapshot = OUTPUT / 'snapshots' / key / 'inventory.json'
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    if snapshot.exists() and snapshot.read_bytes() != raw:
        raise ValueError('Immutable inventory archive differs')
    if not snapshot.exists():
        snapshot.write_bytes(raw)
    methods = {str(p): sha(p) for p in (*METHODS,
        Path('src/ls_satsearch/data.py'), Path('src/ls_satsearch/fields.py'))}
    data = Path(os.environ['LS_SAT_DATA'])
    census = {str(p.relative_to(data)): sha(p) for p in
              (data/'resources/census.fits', data/'resources/read_config.yaml')}
    run_id = encoded(dict(inventory=key, methods=methods, census=census,
                          shards=shards, window=window))[:16]
    out = OUTPUT / 'tiled' / run_id
    out.mkdir(parents=True, exist_ok=True)
    records = [r for r in json.loads(raw)['records'] if r['classification'] not in
               ('missing_actual_mask', 'known_recovery_control')]
    if window:
        left, right, low, high = window
        if not 0 <= left < right <= 360 or not -90 <= low < high <= 90:
            raise ValueError('Invalid nonwrapping bounded validation window')
        selected = []
        for record in records:
            center, half, bottom, top = field_bounds(Field(*record['geometry']))
            if bottom > high or top < low or abs((center-(left+right)/2+180)%360-180) > half+(right-left)/2:
                continue
            selected.append(record)
        records = selected
    registration = dict(run_id=run_id, inventory=str(snapshot), inventory_sha256=key,
        method_sha256=methods, census_sha256=census, shards=shards, tile_shards=24, records=records,
        window_ra_dec_deg=window,
        cache=str(data / 'runs/v14/area_polygon_cache'), output=str(out),
        tile_grid=dict(ra_width_deg=10, sin_dec_width=.1, tiles=720),
        scope='Interim mask snapshot, not final production freeze. Exact union of represented cells; no physical-gain or unexplored-area claim.')
    path = out / 'registration.json'
    if path.exists() and json.loads(path.read_text()) != registration:
        raise ValueError('Existing geometry registration changed')
    if not path.exists():
        write_json(path, registration)
    print(path, flush=True)


def cache_key(record, registration):
    # Includes the immutable source manifest and exact geometry implementation.
    # Qualification can improve later without recomputing the same geometry.
    return encoded(dict(manifest=record['manifest_sha256'], raster=record['raster'],
        geometry=record['geometry'], ownership=record['apply_ownership'],
        subdivision=record['subdivision'], region=record['region'],
        method=registration['method_sha256'], census=registration['census_sha256']))


def atomic_json(path, record):
    pending = path.with_suffix('.pending.json')
    write_json(pending, record)
    pending.replace(path)


def vectorize(path, index):
    allocated()
    registration = load(path)
    if not 0 <= index < registration['shards']:
        raise ValueError('Invalid geometry shard')
    census = Census(Path(os.environ['LS_SAT_DATA']))
    data = Path(os.environ['LS_SAT_DATA'])
    for name, checksum in registration['census_sha256'].items():
        if sha(data/name) != checksum:
            raise ValueError('Registered census source changed')
    cache = Path(registration['cache'])
    cache.mkdir(parents=True, exist_ok=True)
    proofs = []
    for record in registration['records'][index::registration['shards']]:
        started = monotonic()
        if sha(Path(record['manifest'])) != record['manifest_sha256']:
            raise ValueError('Mask source manifest changed')
        key = cache_key(record, registration)
        metadata = cache / (key + '.json')
        raster_sha = sha(data / record['raster'])
        if metadata.exists():
            proof = json.loads(metadata.read_text())
            if proof['raster_sha256'] != raster_sha:
                raise ValueError('Cached source raster changed')
            for file, checksum in proof['geometry_sha256'].items():
                if sha(cache / file) != checksum:
                    raise ValueError('Cached geometry changed')
        else:
            geometries, proof = extract(record, data, census)
            files, bounds = {}, []
            for label, geometry in enumerate(geometries):
                file = cache / f'{key}-{label}.wkb'
                pending = file.with_suffix('.pending.wkb')
                pending.write_bytes(shapely.to_wkb(geometry))
                pending.replace(file)
                files[file.name] = sha(file)
                bounds.append(list(geometry.bounds) if not geometry.is_empty else None)
            proof.update(geometry_sha256=files, bounds=bounds)
            atomic_json(metadata, proof)
        proofs.append(dict(field=record['field'], cache_key=key,
            classification=record['classification'], source_area_deg2=record['source_effective_deg2'],
            metadata_sha256=sha(metadata), seconds=monotonic()-started))
        print('MASK_CACHE', index, record['field'], round(proofs[-1]['seconds'], 2), flush=True)
    output = Path(registration['output']) / 'vectors'
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / f'{index:03d}.json', dict(job=os.environ['SLURM_JOB_ID'],
        registration_sha256=sha(path), records=proofs))


def vector_proofs(registration, path):
    proofs = {}
    for index in range(registration['shards']):
        source = Path(registration['output']) / 'vectors' / f'{index:03d}.json'
        saved = json.loads(source.read_text())
        if saved['registration_sha256'] != sha(path):
            raise ValueError('Vector shard belongs to another inventory')
        for proof in saved['records']:
            key = proof['cache_key']
            if key in proofs and proofs[key]['metadata_sha256'] != proof['metadata_sha256']:
                raise ValueError('Duplicate mask proof has different geometry')
            proofs[key] = proof
    expected = {cache_key(r, registration) for r in registration['records']}
    if set(proofs) != expected:
        raise ValueError('Missing or extraneous polygon cache record')
    return proofs


def build_index(path):
    allocated()
    registration = load(path)
    proofs = vector_proofs(registration, path)
    cache = Path(registration['cache'])
    records = []
    for record in registration['records']:
        key = cache_key(record, registration)
        metadata = cache/(key+'.json')
        if sha(metadata) != proofs[key]['metadata_sha256']:
            raise ValueError('Polygon cache proof changed')
        proof = json.loads(metadata.read_text())
        records.append(dict(cache_key=key, classification=record['classification'],
            bounds=proof['bounds'], geometry_sha256=proof['geometry_sha256']))
    atomic_json(Path(registration['output'])/'vector_index.json',
        dict(registration_sha256=sha(path), records=records))
    print('MASK_VECTOR_INDEX', len(records), flush=True)


def tile(path, index):
    allocated()
    start = monotonic()
    registration = load(path)
    if not 0 <= index < 720:
        raise ValueError('Invalid equal-area tile')
    index_path = Path(registration['output'])/'vector_index.json'
    index_hash = sha(index_path)
    vector_index = json.loads(index_path.read_text())
    if vector_index['registration_sha256'] != sha(path):
        raise ValueError('Polygon index belongs to another inventory')
    x, y = index % 36, index // 36
    bounds = (x*10, -1+y*.1, (x+1)*10, min(1., -1+(y+1)*.1))
    clip = box(*bounds)
    if registration['window_ra_dec_deg']:
        left, right, low, high = registration['window_ra_dec_deg']
        clip = clip.intersection(box(left, np.sin(low*RAD), right, np.sin(high*RAD)))
    layers = {key: [[] for _ in range(4)] for key in
              ('all_ordinary_scanned', 'qualified_production')}
    cache = Path(registration['cache'])
    for record in vector_index['records']:
        if clip.is_empty:
            break
        key = record['cache_key']
        for label, bound in enumerate(record['bounds']):
            if bound is None or bound[2] <= bounds[0] or bound[0] >= bounds[2] or bound[3] <= bounds[1] or bound[1] >= bounds[3]:
                continue
            file = cache / f'{key}-{label}.wkb'
            if sha(file) != record['geometry_sha256'][file.name]:
                raise ValueError('Vectorized geometry changed')
            geometry = shapely.from_wkb(file.read_bytes()).intersection(clip)
            layers['all_ordinary_scanned'][label].append(geometry)
            if record['classification'] == 'qualified_discovery':
                layers['qualified_production'][label].append(geometry)
    rows = []
    for layer, parts in layers.items():
        unions = [shapely.union_all(items) for items in parts]
        total = shapely.union_all(unions)
        ambiguity = shapely.union_all([unions[i].intersection(unions[j])
                                      for i in range(4) for j in range(i)])
        surveys = []
        for label, geometry in enumerate(unions):
            other = shapely.union_all([g for j, g in enumerate(unions) if j != label])
            surveys.append(dict(census_label=label,
                represented_label_union_deg2=geometry.area/RAD,
                unambiguous_deg2=geometry.difference(other).area/RAD))
        rows.append(dict(layer=layer, union_deg2=total.area/RAD,
            summed_record_pieces_deg2=sum(g.area for items in parts for g in items)/RAD,
            census_boundary_ambiguity_deg2=ambiguity.area/RAD, census=surveys))
    output = Path(registration['output']) / 'tiles'
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / f'{index:03d}.json', dict(job=os.environ['SLURM_JOB_ID'],
        tile=index, bounds_ra_sindec=bounds, registration_sha256=sha(path),
        vector_index_sha256=index_hash, layers=rows, seconds=monotonic()-start))
    print('ACTUAL_MASK_TILE', index, rows, flush=True)


def collect(path):
    allocated()
    registration = load(path)
    vector_proofs(registration, path)
    index_path = Path(registration['output'])/'vector_index.json'
    index_hash = sha(index_path)
    output = Path(registration['output'])
    rows, inputs = [], {str(path): sha(path)}
    totals = {}
    for index in range(720):
        source = output / 'tiles' / f'{index:03d}.json'
        saved = json.loads(source.read_text())
        if (saved['registration_sha256'] != sha(path) or saved['tile'] != index or
                saved['vector_index_sha256'] != index_hash):
            raise ValueError('Tile provenance mismatch')
        inputs[str(source)] = sha(source)
        for row in saved['layers']:
            rows.append(dict(tile=index, **{k:v for k,v in row.items() if k != 'census'}))
            summed = totals.setdefault(row['layer'], dict(union_deg2=0.,
                summed_record_pieces_deg2=0., census_boundary_ambiguity_deg2=0.,
                census=[dict(census_label=j, represented_label_union_deg2=0., unambiguous_deg2=0.) for j in range(4)]))
            for key in ('union_deg2', 'summed_record_pieces_deg2', 'census_boundary_ambiguity_deg2'):
                summed[key] += row[key]
            for j in range(4):
                for key in ('represented_label_union_deg2', 'unambiguous_deg2'):
                    summed['census'][j][key] += row['census'][j][key]
    write_csv(output / 'tile_areas.csv', rows)
    write_json(output / 'summary.json', dict(job=os.environ['SLURM_JOB_ID'],
        utc=datetime.now(timezone.utc).isoformat(), layers=totals, tiles=720,
        input_sha256=inputs, final_production_frozen=False,
        scope=registration['scope'] + ' Tile interiors are disjoint in RA/sinDec, so exact represented-cell union areas add; shared edges have zero area.'))
    print('FULL_SNAPSHOT_WORKING_MASK_UNION', totals, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'vectorize', 'index', 'tile', 'tile_shard', 'collect'))
    parser.add_argument('--registration', type=Path)
    parser.add_argument('--index', type=int)
    parser.add_argument('--shards', type=int, default=32)
    parser.add_argument('--inventory', type=Path, default=OUTPUT/'inventory.json')
    parser.add_argument('--window', type=float, nargs=4)
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare(args.shards, args.inventory, args.window)
    elif args.mode == 'index':
        build_index(args.registration)
    elif args.mode == 'collect':
        collect(args.registration)
    elif args.mode == 'tile_shard':
        registration = load(args.registration)
        if not 0 <= args.index < registration['tile_shards']:
            raise ValueError('Invalid tile shard')
        for index in range(args.index, 720, registration['tile_shards']):
            tile(args.registration, index)
    else:
        {'vectorize': vectorize, 'tile': tile}[args.mode](args.registration, args.index)
