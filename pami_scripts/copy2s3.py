#!/usr/bin/env python3

import argparse
import os
import subprocess
import bagit
import glob
import shutil

def get_args():
    parser = argparse.ArgumentParser(description='Transcode directories of video files')
    parser.add_argument('-s', '--source',
                        help = 'path to the source directory of bags', required=True)
    #parser.add_argument('-d', '--destination',
    #                    help = 'path to the output directory', required=True)
    args = parser.parse_args()
    return args

def get_directories(args):
    try:
        test_directory = os.listdir(args.source)
    except OSError:
        exit('please retry with a valid directory of files')

    bags = []

    if args.source:
        directory_path = os.path.abspath(args.source)
        for path in os.listdir(directory_path):
            if not path.startswith(('.', '$')):
                path = os.path.join(directory_path, path)
                if os.path.isdir(path):
                    bags.append(path)
    #if os.path.exists(args.destination):
    #    destination_directory = os.path.abspath(args.destination)
    #else:
    #    raise OSError("No such directory")
    return bags

def get_file_list(source_directory):
    file_list = []

    for root, dirs, files in os.walk(source_directory):
        for file in files:
            if file.endswith(('sc.mp4', 'sc.json', 'em.wav', 'em.json', 'em.flac')):
                item_path = os.path.join(root, file)
                file_list.append(item_path)

    return file_list

def cp_files(file_list):
    for filename in sorted(file_list):
        cp_command = [
            'aws', 's3', 'cp',
            filename,
            's3://ami-service-copies'
            ]
        print(cp_command)
        subprocess.call(cp_command)

def main():
    arguments = get_args()
    bags = get_directories(arguments)
    for bag in bags:
        print("now working on: {}".format(bag))
        list_of_files = get_file_list(bag)
        cp_files(list_of_files)

if __name__ == '__main__':
    main()
    exit(0)
