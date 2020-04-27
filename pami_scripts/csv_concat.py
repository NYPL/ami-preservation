#!/usr/bin/env python3

import shutil
import sys
import glob
import argparse
import os

def _make_parser():
    parser = argparse.ArgumentParser(description="concat a bunch of csvs")
    parser.add_argument("-d", "--directory",
                        help = "path to folder full of media files",
                        required = False)
    parser.add_argument("-o", "--output",
                        help = "path to save csv",
                       required = True)

    return parser

def main():
    parser = _make_parser()
    args = parser.parse_args()

    if args.directory:
        if os.path.isdir(args.directory):
            path = args.directory
            allFiles = glob.glob(path + "/*.csv")

    with open(args.output, 'wb') as outfile:
        for i, fname in enumerate(allFiles):
            with open(fname, 'rb') as infile:
                if i != 0:
                    infile.readline()  # Throw away header on all but first file
                    # Block copy rest of file from input to output without parsing
                shutil.copyfileobj(infile, outfile)
                print(fname + " has been imported.")

if __name__ == "__main__":
    main()
