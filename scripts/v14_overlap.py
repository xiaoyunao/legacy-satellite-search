"""Compare separate BASS and DECam catalogs on the same exposed sky."""
import argparse
import json
import os
from pathlib import Path

from astropy.coordinates import SkyCoord
import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
import yaml

from ls_satsearch.data import load_bricks, select
from ls_satsearch.group_budget import groups
from ls_satsearch.run import coverage_metrics, field_cache, read_csv, settings, write_csv, write_json
from ls_satsearch.search import load_isochrone, scan
from v12_footprint import save


def run(identifier):
    root, data, _ = settings()
    spec = next(r for r in read_csv(Path('configs/v14/overlap.csv')) if r['id'] == identifier)
    spec = dict(id='v14_' + identifier, ra=float(spec['ra_deg']), dec=float(spec['dec_deg']),
                width=float(spec['width_deg']), buffer_arcmin=100)
    table = {}
    for region in ('north', 'south'):
        cohort = 'north' if region == 'north' else 'south_delve'
        cfg = yaml.safe_load(Path(f'configs/v12/cohorts/{cohort}/search.yaml').read_text())
        cfg['regional_primary'] = False
        table[region] = cfg, field_cache(root, data, spec, cfg, load_bricks(root, region))
    common = table['north'][1][2] & table['south'][1][2]
    output = Path('results/v14/overlap') / identifier
    output.mkdir(exist_ok=True, parents=True)
    status = dict(job=os.getenv('SLURM_JOB_ID'), spec=spec, conditions={}, overlap_scope='Independent native gr measurements on common exposure and mask coverage.')
    inputs = {}
    fig, axes = plt.subplots(1, 2, figsize=(8,4), sharex=True, sharey=True, layout='constrained')
    peaks = {}
    sky = {}
    for ax, (region, (cfg, (field, src, native, provenance))) in zip(axes, table.items()):
        common_area = coverage_metrics(field, common, cfg)[0]
        status['common_area_deg2'] = common_area
        sample, _, good, magnitudes, selected = select(src, field, common, cfg)
        bound = np.all(abs(sample[:, :2]) < field.width * 30, axis=1)
        inner = sample[bound]
        inside = np.all(abs(np.array(field.xy(src['RA'], src['DEC']))) < field.width * 30, axis=0)
        sky[region] = (SkyCoord(src['RA'][inside & selected], src['DEC'][inside & selected], unit='deg'),
                       magnitudes[inside & selected])
        status['conditions'][region] = dict(
            psf=len(inner), other=int((inside & good & ~selected).sum()),
            area_deg2=coverage_metrics(field, native, cfg)[0],
            g_seeing_median=float(np.median(src['PSFSIZE_G'][inside & selected])) if len(inner) else None)
        inputs[region] = provenance
        if common_area and len(inner):
            ax.hist2d(inner[:,2] - inner[:,3], inner[:,2], bins=[90,100], range=[[-.6,2.4],[17,24]],
                      cmap='magma', norm='log')
            model = load_isochrone(data / 'resources' / cfg['isochrone'])
            _, rows, _, _ = scan(sample, field, common, model, cfg)
            shared = [dict(r, ranking=r['score'],channel='A_base') for r in rows if r['branch']=='main']
            cut_path = Path('results/v11/north/main/calibration/sky_group_policy.json' if region == 'north'
                            else 'configs/v7/production.json')
            cut = next(r['cutoff'] for r in json.loads(cut_path.read_text())['thresholds'] if r['budget']==.3)
            peaks[region] = [a for a, _ in groups(shared) if a['ranking'] >= cut]
        else:
            peaks[region] = []
        ax.set_title(region.title())
        ax.set_xlabel(r'$g_0-r_0$')
    if len(sky['north'][0]) and len(sky['south'][0]):
        an, gn = sky['north']
        a_s, gs = sky['south']
        into, sep, _ = an.match_to_catalog_sky(a_s)
        reverse = a_s.match_to_catalog_sky(an)[0]
        match = (sep.arcsec < .8) & (reverse[into] == np.arange(len(an)))
        status['psf_mutual_matches_within_0p8arcsec'] = int(match.sum())
        if match.any():
            status['median_north_minus_south_g_r'] = np.median(gn[match] - gs[into[match]], axis=0).tolist()
    axes[0].set_ylabel(r'$g_0$')
    axes[0].invert_yaxis()
    save(fig, output / 'common_cmd')
    pairs = []
    for region, rows in peaks.items():
        other = peaks['south' if region == 'north' else 'north']
        coords = SkyCoord([r['ra_deg'] for r in other], [r['dec_deg'] for r in other], unit='deg')
        for row in rows:
            angular = SkyCoord(row['ra_deg'], row['dec_deg'], unit='deg').separation(coords).arcmin
            for i in np.flatnonzero(angular <= 5):
                pairs.append(dict(region=region, ra_deg=row['ra_deg'], dec_deg=row['dec_deg'],
                                  dm=row['dm'], rh_arcmin=row['rh_arcmin'], score=row['score'],
                                  separation_arcmin=float(angular[i]), other_dm=other[i]['dm'],
                                  other_score=other[i]['score']))
    known = read_csv(Path('references/benchmarks.csv'))
    centers = SkyCoord([float(r['ra_deg']) for r in known], [float(r['dec_deg']) for r in known], unit='deg')
    targets = []
    for i, row in enumerate(known):
        x, y = field.xy(float(row['ra_deg']), float(row['dec_deg']))
        if not max(abs(x),abs(y)) < field.width * 30:
            continue
        for region, rows in peaks.items():
            nearby = [r for r in rows if centers[i].separation(SkyCoord(r['ra_deg'],r['dec_deg'],unit='deg')).arcmin <= 5]
            targets.append(dict(name=row['name'], region=region, associated_groups=len(nearby),
                                nearest_dm=nearby[0]['dm'] if nearby else None))
    status.update(groups={r:len(v) for r,v in peaks.items()}, inputs=inputs)
    write_json(output/'comparison.json', status)
    write_csv(output/'peak_pairs.csv', pairs, keys=('region','ra_deg','dec_deg'))
    write_csv(output/'known_controls.csv', targets, keys=('name','region'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('identifier')
    run(p.parse_args().identifier)
