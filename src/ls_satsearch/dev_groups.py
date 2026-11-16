"""Calibrate fresh development blocks before opening the holdout."""

import argparse
from pathlib import Path

import yaml

from .group_budget import evaluate
from .run import config_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    fields = yaml.safe_load(config_path('fields.yaml').read_text())['fields']
    ids = [r['id'] for r in fields if r['role']=='pilot_dev']
    summary = Path('results/summary')
    dest = Path('results/development_groups')
    evaluate(summary, dest/'all_A', expected_dev=ids)
    evaluate(summary, dest/'AB_controls', expected_dev=ids,
             channels_only=('A_base','A_deep','B_base','B_deep'))


if __name__=='__main__':
    main()
