#!/usr/bin/env python3

import argparse
import os
import subprocess
import bagit
import glob
import shutil

def get_args():
    parser = argparse.ArgumentParser(description='Transcode a directory of video files')
    parser.add_argument('-s', '--source',
                        help = 'path to the source directory files', required=True)
    parser.add_argument('-d', '--destination',
                        help = 'path to the output directory', required=True)
    args = parser.parse_args()
    return args

def get_directory(args):
    try:
        test_directory = os.listdir(args.source)
    except OSError:
        exit('please retry with a valid directory of video files')
    source_directory = args.source
    if os.path.exists(args.destination):
        destination_directory = os.path.abspath(args.destination)
    else:
        raise OSError("No such directory")
    return source_directory, destination_directory

def sep_files(source_directory, destination_directory):
    files = glob.iglob(os.path.join(source_directory, '*mp4'))
    for file in files:
        framerate = subprocess.check_output(
            [
                'mediainfo', '--Language=raw',
                '--Full', "--Inform=Video;%FrameRate%",
                file
            ]
            ).rstrip()
        if framerate.decode('UTF-8') == "25.000":
            shutil.move(file, destination_directory)

def main():
    arguments = get_args()
    source, destination = get_directory(arguments)
    files = sep_files(source, destination)

if __name__ == '__main__':
    main()
    exit(0)
