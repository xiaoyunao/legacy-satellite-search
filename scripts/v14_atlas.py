"""Plot registered survey conditions and the measured DR11 raster union in both frames."""
import os
from pathlib import Path

from astropy.coordinates import SkyCoord
import matplotlib.pyplot as plt
import numpy as np
import yaml
from scipy.spatial import cKDTree

from ls_satsearch.coverage_history import covered, inventory
from ls_satsearch.data import load_bricks
from ls_satsearch.expansion import unit
from ls_satsearch.run import read_csv, sha, write_csv, write_json
from v12_footprint import save


def mark_new(data, records, grid, region):
    ra, dec = grid['ra'], grid['dec']
    order = np.argsort(dec)
    d = dec[order]
    result = np.zeros(len(ra), dtype=bool)
    scan_owner = np.full(len(ra), '', dtype='<U80')
    for r in records:
        if r['region'] != region:
            continue
        i, j = np.searchsorted(d, r['bounds'][2:])
        where = order[i:j]
        category = r['survey']
        accepted = ({category: grid['census'][where] == category}
                    if region == 'south' and category is not None else None)
        seen = covered(data, [r], ra[where], dec[where], accepted)
        selected = where[seen]
        result[selected] = True
        scan_owner[selected] = r['field']
    return result, scan_owner


def coordinates(ra, dec, frame):
    if frame == 'galactic':
        sky = SkyCoord(ra, dec, unit='deg').galactic
        return -sky.l.wrap_at('180d').rad, sky.b.rad
    return np.deg2rad(180-np.asarray(ra)), np.deg2rad(dec)


def render(output, frame, table, candidates):
    x,y = coordinates(table['ra'],table['dec'],frame)
    canvas,axes = plt.subplots(4,2,figsize=(11,15),layout='constrained',
                               subplot_kw=dict(projection='mollweide'))
    layers = ('North BASS','South PS1','South DELVE','South DES','South outside census','North-only seam')
    colors = ['#365989','#31734d','#bd6a32','#80466b','#a3a3a3','#3399a0']
    ax = axes.flat[0]
    for i, (label, color) in enumerate(zip(layers, colors)):
        use = table['layer']==i
        ax.scatter(x[use],y[use],c=color,s=.6,rasterized=True,label=label,linewidth=0)
    ax.set_title('DR11 brick-based gr footprint')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.10),fontsize=7,frameon=False,ncol=3)
    ax=axes.flat[1]
    render_order = ((~table['clean']&~table['seen'],'#f0dece','Extension, awaiting valid scan'),
                    (table['clean']&~table['seen'],'#d6d9dd','Primary, awaiting valid scan'),
                    (~table['clean']&table['seen'],'#a66b44','Measured extension'),
                    (table['clean']&table['seen']&~table['new'],'#88a3c4','Previously measured primary'),
                    (table['clean']&table['new'],'#274a7d','New measured primary'))
    for use,color,label in render_order:
        ax.scatter(x[use],y[use],c=color,s=.6,rasterized=True,label=label,linewidth=0)
    for grade,shape,mark in (('known_system_response','^','#1f602e'),('priority_L0','D','#991d61')):
        rows=[r for r in candidates if r['grade']==grade]
        if rows:
            a,d = coordinates([float(r['ra_deg']) for r in rows],[float(r['dec_deg']) for r in rows],frame)
            ax.scatter(a,d,marker=shape,c=mark,s=15,label=grade.replace('_',' '),zorder=4,linewidth=.4)
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.10),fontsize=7,frameon=False,ncol=2)
    ax.set_title('Completed gr masks and reviewed positions')
    for axis,key,label,limits in zip(list(axes.flat)[2:],('g_depth','r_depth','g_seeing','r_seeing','ebv','density'),
                       ('g PSF depth, 5σ mag','r PSF depth, 5σ mag','g seeing, arcsec','r seeing, arcsec',
                        'E(B−V), mag','log₁₀ selected PSF density, deg⁻²'),
                       ((22,26),(22,26),(.8,2.4),(.8,2.4),(0,.4),(2.8,4.8))):
        ok = np.isfinite(table[key])
        if key == 'density':
            axis.scatter(x,y,s=.6,c='#e2e4e6',rasterized=True,linewidth=0)
        points=axis.scatter(x[ok],y[ok],c=table[key][ok],s=.6,cmap='viridis',vmin=limits[0],vmax=limits[1],
                            rasterized=True,linewidth=0)
        canvas.colorbar(points,ax=axis,orientation='horizontal',fraction=.05,pad=.10)
        axis.set_title(label)
    ticks=np.deg2rad(np.arange(-120.,121.,60))
    labels=['120°','60°','0°','300°','240°'] if frame=='galactic' else ['20h','16h','12h','8h','4h']
    for axis in axes.flat:
        axis.set_xticks(ticks,labels)
        axis.grid(alpha=.20)
        axis.tick_params(labelsize=8)
    save(canvas,output/f'dr11_{frame}')


def run(output):
    root = Path(os.environ['LS_SAT_DATA'])
    storage = root/'runs/v14'
    rasters = inventory(Path.cwd(),root)
    observed = [r for r in rasters if r['field'].startswith('v14_') and 'raster' in r]
    plan = yaml.safe_load(Path('configs/v14/full_plan.yaml').read_text())
    area = 360**2 / np.pi / (12 * plan['nside']**2)
    rows, maps = [], []
    metrics = {}
    for p in Path('results/v14/discovery').glob('*/fields.csv'):
        metrics.update({r['field']:r for r in read_csv(p) if r['status']=='complete'})
    for v in ('v12','v13'):
        for path in Path(f'results/{v}/discovery').glob('*/*/field_metrics.csv'):
            for row in read_csv(path):
                if row.get('source_metadata_scope') == 'full core before ownership':
                    continue
                metrics[row['field']] = dict(psf=row['inner_psf'],background_core_deg2=row['area_deg2'])
    archive = [r for r in rasters if r['field'] in metrics and not r['field'].startswith('v14_')]
    for region in ('south','north'):
        grid = dict(np.load(storage/f'{region}_brick_grid.npz',allow_pickle=False))
        layer = np.zeros(len(grid['ra']), dtype=np.uint8)
        if region=='south':
            layer = np.array([4,3,2,1],dtype=np.uint8)[grid['census']]
        grid['new'], owner = mark_new(root,observed,grid,region)
        grid['layer'] = layer
        grid['seen'] = grid['observed'] | grid['new']
        _, prior_owner = mark_new(root,archive,grid,region)
        owner[owner==''] = prior_owner[owner=='']
        grid['density'] = np.full(len(layer), np.nan)
        for f in np.unique(owner):
            m = metrics.get(f)
            if not m or not m['psf'] or float(m['psf']) <= 0:
                continue
            # Use per-field selected source density from the full search core
            # with the original (not residual-owned) effective area denominator.
            if not m.get('background_core_deg2'):
                continue
            grid['density'][owner==f] = np.log10(float(m['psf'])/float(m['background_core_deg2']))
        maps.append(grid)
        for code in np.unique(layer):
            for quality in ('primary','extension'):
                use = (layer==code) & (grid['clean']==(quality=='primary'))
                rows.append(dict(layer=int(code),quality=quality, brick_proxy_deg2=area*use.sum(),
                                 previous_raster_union_proxy_deg2=area*(use&grid['observed']).sum(),
                                 new_raster_union_proxy_deg2=area*(use&grid['new']&~grid['observed']).sum(),
                                 unobserved_proxy_deg2=area*(use&~grid['seen']).sum()))

    fallback = storage/'north_outside_primary.npz'
    if fallback.is_file():
        with np.load(fallback,allow_pickle=False) as sky:
            ra,dec = sky['ra'],sky['dec']
        if len(ra):
            root_dir = Path(os.environ['LS_DR11_ROOT'])
            bricks = load_bricks(root_dir,'north')
            good=(bricks['PSFDEPTH_G']>0)&(bricks['PSFDEPTH_R']>0)
            bricks=bricks[good]
            _, near = cKDTree(unit(bricks['RA'],bricks['DEC'])).query(unit(ra,dec))
            b=bricks[near]
            extra=dict(ra=ra,dec=dec,clean=np.zeros(len(ra),bool),layer=np.full(len(ra),5),
                       g_depth=b['PSFDEPTH_G'],r_depth=b['PSFDEPTH_R'],
                       g_seeing=b['PSFSIZE_G'],r_seeing=b['PSFSIZE_R'],ebv=b['EBV'],
                       observed=np.zeros(len(ra),bool),density=np.full(len(ra),np.nan))
            supplemental=[r for r in observed if 'north_single_native' in r['field']]
            extra['new'], _ = mark_new(root,supplemental,extra,'north')
            extra['seen'] = extra['new']
            maps.append(extra)
            rows.append(dict(layer=5,quality='extension',brick_proxy_deg2=area*len(ra),
                             previous_raster_union_proxy_deg2=0.,
                             new_raster_union_proxy_deg2=area*extra['seen'].sum(),
                             unobserved_proxy_deg2=area*(~extra['seen']).sum()))

    data = {k:np.concatenate([m[k] for m in maps]) for k in maps[0] if k!='census'}
    output.mkdir(exist_ok=True,parents=True)
    catalogue=Path('results/v14/catalogue/candidate_catalogue.csv')
    candidates=read_csv(catalogue) if catalogue.exists() else []
    write_csv(output/'raster_union.csv',rows)
    write_json(output/'manifest.json',dict(job=os.getenv('SLURM_JOB_ID'),nside=plan['nside'],
               new_measured_raster_count=len(observed),catalogue_sha256=sha(catalogue) if candidates else None,
               current_manifest_hashes={r['field']:r['manifest_sha256'] for r in observed},
               note='Coarse HEALPix sky rendering of exposure-based search rasters. Per-field area comes from the native WCS search mask. Blank sky has no sampled two-band brick coverage.'))
    with plt.rc_context({'font.family':'serif','font.size':9,'svg.fonttype':'none','pdf.fonttype':42}):
        for frame in ('icrs','galactic'):
            render(output, frame, data, candidates)


if __name__ == '__main__':
    run(Path('results/v14/atlas'))
