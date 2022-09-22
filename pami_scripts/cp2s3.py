#!/usr/bin/env python3

import argparse
import os
import subprocess
import bagit
import glob
import shutil

def get_args():
    parser = argparse.ArgumentParser(description='Copy SC Video and EM Audio to AWS')
    parser.add_argument('-d', '--directory',
                        help = 'path to directory of bags', required=True)
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
    return bags

def get_file_list(source_directory):
    file_list = []

    for root, dirs, files in os.walk(source_directory):
        for file in files:
            if file.endswith(('sc.mp4', 'sc.json', 'em.wav', 'em.flac', 'em.json')):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_list.append(item_path)

    return file_list

def cp_files(file_list):
    for filename in sorted(file_list):
        cp_command = [
            'aws', 's3', 'cp',
            filename,
            's3://ami-carnegie-servicecopies'
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
