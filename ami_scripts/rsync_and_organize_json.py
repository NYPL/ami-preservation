#!/usr/bin/env python3

import os
import subprocess
from pathlib import Path
from multiprocessing import Pool, cpu_count
from functools import partial
import argparse

def rsync_file(dst_dir, json_file):
    # split the file name into parts
    parts = json_file.stem.split('_')
    
    # check if the filename has at least two parts
    if len(parts) < 2:
        print(f"Skipping file {json_file} as it does not meet the expected format.")
        return

    # create a subdirectory path based on the first three digits of the file name
    subdir = dst_dir / parts[1][:3]
    
    # create the subdirectory if it does not exist
    subdir.mkdir(parents=True, exist_ok=True)

    # rsync the file into the subdirectory
    subprocess.run(['rsync', '-av', str(json_file), str(subdir)], check=True)

def main():
    parser = argparse.ArgumentParser(description='Rsync JSON files into subdirectories.')
    parser.add_argument('-s', '--source', required=True, help='Source directory containing JSON files.')
    parser.add_argument('-d', '--destination', required=True, help='Destination directory to rsync files to.')
    args = parser.parse_args()

    # convert source and destination directories to Path objects
    src_dir = Path(args.source)
    dst_dir = Path(args.destination)

    # create the destination directory if it does not exist
    dst_dir.mkdir(parents=True, exist_ok=True)

    # get a list of all JSON files in the source directory and subdirectories
    json_files = list(src_dir.glob('**/*.json'))

    # use a Pool of processes to rsync the files
    with Pool(processes=cpu_count()) as pool:
        pool.map(partial(rsync_file, dst_dir), json_files)

if __name__ == "__main__":
    main()
