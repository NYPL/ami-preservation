#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path
from multiprocessing import Pool
from functools import partial

def rsync_file(dst_dir, json_file):
    parts = json_file.stem.split('_')
    subdir = dst_dir / parts[1][:3]
    subdir.mkdir(parents=True, exist_ok=True)
    subprocess.run(['rsync', '-av', str(json_file), str(subdir)], check=True)

def main():
    # create the argument parser
    parser = argparse.ArgumentParser(description="Rsync JSON files into subdirectories based on filename.")
    parser.add_argument('-s', '--source', required=True, help="Source directory")
    parser.add_argument('-d', '--destination', required=True, help="Destination directory")

    # parse the arguments
    args = parser.parse_args()

    # source and destination directories
    src_dir = Path(args.source)
    dst_dir = Path(args.destination)

    # create the destination directory if it does not exist
    dst_dir.mkdir(parents=True, exist_ok=True)

    # list of JSON files
    json_files = list(src_dir.glob('**/*.json'))

    # create a multiprocessing pool and rsync files in parallel
    with Pool(processes=4) as pool:  # only use 4 processes
        pool.map(partial(rsync_file, dst_dir), json_files)

if __name__ == '__main__':
    main()
