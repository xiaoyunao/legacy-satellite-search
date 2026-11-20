"""Run the compiled official single-band operator on one acquired native blank.

This is a technical I/O/recipe preflight, not DR2 stack equivalence or response.
All image, configuration dump, source catalogue and console outputs stay scratch.
"""
import json
import os
from pathlib import Path
import subprocess
import time

from astropy.io import fits
from ls_satsearch.run import sha, write_json


def main():
    if not os.getenv('SLURM_JOB_ID'):
        raise RuntimeError('Native PS1 preflight requires Slurm')
    manifest = Path('results/v14/ps1_ipp/blank_pilot/acquisition.json')
    acquisition = json.loads(manifest.read_text())
    data = Path(os.environ['LS_SAT_DATA'])
    source = data / 'software/ipp/ipp-20190404'
    prefix = data / 'software/ipp/install/lssat.lin64'
    root = data / 'resources/v14/ps1_operator/preflight' / os.environ['SLURM_JOB_ID']
    root.mkdir(parents=True, exist_ok=False)
    config = source / 'ippconfig'
    # Use the archived system/camera/recipe files directly, without ~/.ipprc.
    rc = root / 'ipprc.config'
    rc.write_text(f'PATH STR {config}\nSITE STR {config}/site.config.in\n'
                  f'SYSTEM STR {config}/system.config\nLOGLEVEL S32 3\n'
                  'LOGDEST STR STDERR\nTRACEDEST STR STDERR\n')
    products = {p['type']: p for p in acquisition['products'] if p['filter'] == 'g'}
    inputs = {}
    for kind in ('stack', 'stack.mask', 'stack.wt'):
        item = products[kind]
        path = Path(item['path'])
        if sha(path) != item['sha256']:
            raise ValueError(f'Acquired product changed: {kind}')
        inputs[kind] = {'sha256': item['sha256'], 'path': str(path)}
    # Preserve identifying/processing header metadata, never per-source rows.
    with fits.open(products['stack']['path']) as hd:
        header = hd[0].header
        keys = ('FPA', 'INSTR', 'INSTRUME', 'PSCAMERA', 'EXTNAME', 'HIERARCH FPA.INSTRUMENT',
                'HIERARCH FPA.FILTER', 'HIERARCH FPA.ZP', 'HIERARCH FPA.PHOTCODE',
                'FLUXMAG0', 'MAGZP', 'MJD-OBS', 'EXPTIME', 'BOFFSET', 'BSOFTEN')
        native_header = {k: header.get(k) for k in keys}
    command = [str(prefix / 'bin/psphot'), '-ipprc', str(rc), '-nthreads', '4',
               '-file', products['stack']['path'], '-mask', products['stack.mask']['path'],
               '-variance', products['stack.wt']['path'], '-dumpconfig', str(root / 'effective.config'),
               str(root / 'native_g')]
    start = time.monotonic()
    with (root / 'operator.log').open('w') as stream:
        try:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=1400)
            status = result.returncode
        except subprocess.TimeoutExpired:
            status = 'timeout'
    artifacts = {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)}
                 for p in root.iterdir() if p.is_file()}
    write_json(Path('results/v14/ps1_ipp/blank_pilot/preflight.json'), {
        'job': os.environ['SLURM_JOB_ID'], 'command': command, 'returncode': status,
        'elapsed_s': time.monotonic() - start, 'acquisition_sha256': sha(manifest),
        'runner_sha256': sha(Path(__file__)), 'binary_sha256': sha(prefix / 'bin/psphot'),
        'inputs': inputs, 'native_header': native_header, 'artifacts': artifacts,
        'raw_output_root': str(root), 'native_processing_attempted': True,
        'physical_PS1_response_validated': False,
        'scope': 'Single-band official psphot technical preflight with archived defaults. '
                 'Not five-band psphotStack, DR2 configuration/photometry equivalence, injection '
                 'response, independent candidate confirmation, or physical LS-minus-PS1 gain.'})
    print(json.dumps({'job': os.environ['SLURM_JOB_ID'], 'returncode': status,
                      'elapsed_s': time.monotonic() - start}))


if __name__ == '__main__':
    main()
