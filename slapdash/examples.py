#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# Created: 01/2022
# Author: Carmelo Mordini <cmordini@phys.ethz.ch>
import argparse
import runpy
from pathlib import Path

examples = Path(__file__).parent / 'examples'


def get_examples():
    return sorted(p.stem for p in examples.iterdir() if p.suffix == '.py')


def list_examples():
    print("Available examples")
    print("\n".join(f"- {name}" for name in get_examples()))


def run_example(path):
    runpy.run_path(str((examples / path).with_suffix('.py')), run_name='__main__')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("example", nargs="?", default="")
    args = parser.parse_args()
    if args.example:
        run_example(args.example)
    else:
        list_examples()
