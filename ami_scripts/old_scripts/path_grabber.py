#!/usr/bin/env python3

import argparse
import os
import glob
import logging
import csv
import re

LOGGER = logging.getLogger(__name__)

def _make_parser():
    parser = argparse.ArgumentParser(description="Pull MediaInfo from a bunch of video or audio files")
    parser.add_argument("-d", "--directory",
                        help = "path to folder full of media files",
                        required = False)
    parser.add_argument("-f", "--file",
                        help = "path to folder full of media files",
                        required = False)
    parser.add_argument("-o", "--output",
                        help = "path to save csv",
                        required = True)


    return parser


def main():
    parser = _make_parser()
    args = parser.parse_args()

    files_to_examine = []

    #validate that dir exists and add all files to queue
    if args.directory:
        if os.path.isdir(args.directory):
            glob_abspath = os.path.abspath(os.path.join(args.directory, '**/*'))
            for filename in glob.glob(glob_abspath, recursive = True):
                if filename.endswith(('.mkv', '.mov', '.json', '.wav', '.WAV', '.mp4', '.dv', '.iso', '.flac')):
                    files_to_examine.append(filename)

    all_data = []
    for file in files_to_examine:
        file_data = [file]
        all_data.append(file_data)

    with open(args.output, 'w') as f:
        md_csv = csv.writer(f)
        md_csv.writerow(['filePath'])
        md_csv.writerows(all_data)

if __name__ == "__main__":
    main()
