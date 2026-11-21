"""Build the fixed comparison roster from pinned author tables."""
import csv
import math
from pathlib import Path
import re
import unicodedata

ROOT=Path('references')
AUTHOR=ROOT/'codex_benchmark_sources'
OUT=ROOT/'census_comparison'
TAN='https://arxiv.org/html/2509.12313v2'


def read(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def key(name):
    name=unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode()
    return re.sub(r'[^a-z0-9]','',name.lower())


def build():
    extended=[]
    for table,cohort in [('offical_delve_census_refgalaxy_list.csv','tan_galaxy'),
                         ('offical_delve_census_refambigous_list.csv','tan_compact')]:
        for row in read(AUTHOR/table):
            strict=(cohort=='tan_galaxy' and row.get('delve_census')=='True'
                    and row['Survey'] in {'DES','DELVE','PS1'})
            distance=float(row['distance'])
            radius=float(row['rhalf_sph_physical']) if row['rhalf_sph_physical'] else None
            arcmin=math.degrees(math.atan(radius/(distance*1000)))*60 if radius else None
            extended.append(dict(name=row['name'],ra_deg=row['ra'],dec_deg=row['dec'],D_kpc=distance,
                M_V=row['M_V'],theta_h_arcmin=arcmin,r_h_pc=radius,published_dm=row['distance_modulus'],
                roster=cohort,tan_assignment=row['Survey'],tan_main_strict=strict,
                tan_compact_detected=row.get('In_Census',''),reference=TAN,source_row=row['key']))
    assert sum(r['tan_main_strict'] for r in extended)==49
    present={key(r['name']) for r in extended}
    for row in read(ROOT/'benchmarks.csv'):
        if key(row['name']) not in present:
            extended.append(dict(row,roster='project_supplement',published_dm='',tan_assignment='',
                tan_main_strict=False,tan_compact_detected='',reference='references/codex_satellite_benchmarks.json',
                source_row=row['name']))
    for row in read(OUT/'euclid_dr1_mw.csv'):
        arcmin=float(row['semimajor_h_arcmin'])*math.sqrt(1-float(row['ellipticity']))
        radius=1000*float(row['D_kpc'])*math.tan(math.radians(arcmin/60))
        extended.append(dict(name=row['name'],ra_deg=row['ra_deg'],dec_deg=row['dec_deg'],
            D_kpc=row['D_kpc'],M_V=row['M_V'],theta_h_arcmin=arcmin,r_h_pc=radius,
            published_dm=row['published_dm'],roster='euclid_DR1_MW',tan_assignment='',
            tan_main_strict=False,tan_compact_detected='',reference=row['reference'],source_row=row['name']))
    with (OUT/'roster.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(extended[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(extended)
    print(dict(total=len(extended),tan_strict=sum(r['tan_main_strict'] for r in extended),
               tan_compact=sum(r['roster']=='tan_compact' for r in extended)))


if __name__=='__main__':
    build()
