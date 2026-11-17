"""Project the PARSEC PS1 template into the Legacy Surveys Bok passbands."""
import argparse
from pathlib import Path

from numpy.polynomial.polynomial import polyval


# Legacy Surveys Imaging Standard Bandpass, 2018-11-15. Historical code stores
# the opposite sign of the correction applied to the incoming PS1 magnitudes.
CORRECTION = {'g': (.00464, .08672, -.00668, -.00255),
              'r': (.00110, -.06875, .02480, -.00855)}


def convert(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    cols = None
    lines = []
    for line in source.read_text().splitlines():
        if line.startswith('#'):
            if 'int_IMF' in line and 'M_ini' in line:
                names = line[1:].split()
                cols = [names.index(b) for b in ('gP1', 'rP1', 'iP1')]
                for b in ('g', 'r'):
                    names[names.index(b + 'P1')] = b
                line = '# ' + ' '.join(names)
            lines.append(line)
        elif line.strip():
            if cols is None:
                raise ValueError('Expected the PS1 PARSEC column header')
            tokens = line.split()
            # Clamp extrapolation to the calibration colour domain.
            color = min(2.7, max(.4, float(tokens[cols[0]]) - float(tokens[cols[2]])))
            for b, col in zip('gr', cols[:2]):
                tokens[col] = f'{float(tokens[col]) + polyval(color, CORRECTION[b]):.7f}'
            lines.append(' '.join(tokens))
    payload = ('# BASS g,r via Legacy Surveys PS1-to-90prime catalogue color terms\n'
               + '\n'.join(lines) + '\n')
    tmp = destination.with_suffix('.tmp')
    tmp.write_text(payload)
    tmp.replace(destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    convert(args.source, args.destination)
