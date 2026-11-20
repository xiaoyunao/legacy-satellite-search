"""Five-band official psphotStack blank preflight on the acquired real skycell.

Use archived defaults and native unconverted science/variance/masks; infer no
physical response or catalogue equivalence from a successful process alone.
"""
import csv
import json
import os
from pathlib import Path
import subprocess
import time

from ls_satsearch.run import sha, write_json


def main():
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Native stack photometry requires Slurm')
    manifest = Path('results/v14/ps1_ipp/blank_pilot/acquisition.json')
    a = json.loads(manifest.read_text())
    data = Path(os.environ['LS_SAT_DATA'])
    source = data / 'software/ipp/ipp-20190404'
    prefix = data / 'software/ipp/install/lssat.lin64'
    root = data / 'resources/v14/ps1_operator/stack_preflight' / os.environ['SLURM_JOB_ID']
    root.mkdir(parents=True, exist_ok=False)
    config = source / 'ippconfig'
    rc = root / 'ipprc.config'
    rc.write_text(f'PATH STR {config}\nSITE STR {config}/site.config.in\n'
                  f'SYSTEM STR {config}/system.config\nLOGLEVEL S32 3\n'
                  'LOGDEST STR STDERR\nTRACEDEST STR STDERR\n')
    references = []
    for p in a['reference_pages']:
        if sha(Path(p['path'])) != p['sha256']:
            raise ValueError('Same-cell reference changed')
        with Path(p['path']).open() as stream:
            references.extend(csv.DictReader(stream))
    blocks = ['INPUT MULTI\n']
    ids, inputs = {}, {}
    for band in 'grizy':
        identifiers = {int(r[band + 'stackImageID']) for r in references if int(r[band + 'stackImageID']) > 0}
        if len(identifiers) != 1:
            raise ValueError(f'Expected one native image identity for {band}, found {len(identifiers)}')
        ids[band] = identifiers.pop()
        blocks.append(f'INPUT METADATA\n  STACK_ID S64 {ids[band]}\n')
        for kind, key in [('stack', 'IMAGE'), ('stack.mask', 'MASK'), ('stack.wt', 'VARIANCE')]:
            item = next(p for p in a['products'] if p['filter'] == band and p['type'] == kind)
            path = Path(item['path'])
            if sha(path) != item['sha256']:
                raise ValueError(f'Acquired native {band}/{kind} changed')
            inputs[str(path)] = item['sha256']
            blocks.append(f'  RAW:{key} STR {path}\n')
        # stack.exp is integrated exposure time, not an exposure-number map.
        # Omit RAW:EXPNUM rather than passing seconds as N_FRAMES.
        blocks.append('END\n')
    table = root / 'inputs.mdc'
    table.write_text(''.join(blocks))
    command = [str(prefix / 'bin/psphotStack'), '-ipprc', str(rc), '-threads', '8',
               '-input', str(table), '-dumpconfig', str(root / 'effective.config'), str(root / 'native_grizy')]
    start = time.monotonic()
    with (root / 'operator.log').open('w') as stream:
        try:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=1400)
            status = result.returncode
        except subprocess.TimeoutExpired:
            status = 'timeout'
    artifacts = {p.name: dict(bytes=p.stat().st_size, sha256=sha(p)) for p in root.iterdir() if p.is_file()}
    write_json(Path('results/v14/ps1_ipp/blank_pilot') / f"stack_preflight_{os.environ['SLURM_JOB_ID']}.json", dict(
        job=os.environ['SLURM_JOB_ID'], returncode=status, elapsed_s=time.monotonic() - start,
        command=command, inputs=inputs, acquisition_sha256=sha(manifest), image_ids_from_same_cell_DR2=ids,
        runner_sha256=sha(Path(__file__)), binary_sha256=sha(prefix / 'bin/psphotStack'),
        source_config_sha256={str(p.relative_to(source)): sha(p) for p in config.rglob('*.config')},
        artifacts=artifacts, raw_output_root=str(root), physical_PS1_response_validated=False,
        DR2_operator_equivalence_validated=False,
        scope='Actual five-band blank operator attempt using archived defaults, not DR2 production configuration identity. '
              'Native asinh decoding is delegated to the official psLib reader; .wt is supplied as VARIANCE. '
              'No convolved inputs are substituted and no exposure-seconds map is treated as exposure count. '
              'Requires actual output/PSF/photometry/selection comparison before injection or response use.'))
    print(json.dumps(dict(job=os.environ['SLURM_JOB_ID'], returncode=status, elapsed_s=time.monotonic() - start)))


if __name__ == '__main__':
    main()
