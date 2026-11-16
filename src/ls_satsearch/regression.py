"""Evaluate revised searches in the previously inspected first-pilot fields."""

from pathlib import Path

from .evaluate import evaluate
from .review import review


def main():
    path=Path('results/summary')
    evaluate(path)
    for field in ('eval_ordinary','eval_deep'):
        for depth in ('base','deep'):
            print(f'{field} {depth}',flush=True)
            review(field,depth,group_limit=3)
    evaluate(path)


if __name__=='__main__':
    main()
