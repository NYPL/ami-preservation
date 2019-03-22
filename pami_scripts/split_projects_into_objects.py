#!/usr/bin/env python3

import argparse
import os
import subprocess
import bagit
import glob
import shutil
import re

def get_args():
    parser = argparse.ArgumentParser(description='Move files into object dirs and bag')
    parser.add_argument('-s', '--source',
                        help = 'path to the source directory files', required=True)
    args = parser.parse_args()
    return args


def get_files(source_directory):
    # Return a list of relative filepath to the source directory
    file_list = []

    for dirpath, _, filenames in os.walk(source_directory):
        for f in filenames:
            rel_path = os.path.relpath(
                os.path.join(dirpath, f), start=source_directory)
            file_list.append(rel_path)

    return file_list


def make_object_dirs(source_directory, file_list):
    # list to report object_dirs created and untouched files
    cms_ids = set()
    unmoved = []

    # extract cms_id from filename and insert into path
    for file_path in file_list:
        try:
            cms_id = re.search(r'_(\d{6})_', file_path).group(1)
            cms_ids.add(cms_id)
        except:
            print('ummm, what is this {}'.format(file_path))
            unmoved.append(file_path)
            continue

        old_file_path = os.path.join(source_directory, file_path)
        new_file_path = os.path.join(source_directory, cms_id, file_path)
        if not os.path.exists(os.path.dirname(new_file_path)):
            os.makedirs(os.path.dirname(new_file_path))
        shutil.move(old_file_path, new_file_path)

    return cms_ids, unmoved


def make_object_bags(source_directory, cms_objects):
    for cms_id in cms_objects:
        bagit.make_bag(os.path.join(source_directory, cms_id), checksums=['md5'])


def clean_up(source_directory):
    for directory in os.listdir(source_directory):
        dir_path = os.path.join(source_directory, directory)
        if os.path.isdir(dir_path):
            if not os.listdir(dir_path):
                print('Deleting empty directory: {}'.format(dir_path))
                os.rmdir(dir_path)


def main():
    arguments = get_args()
    source_directory = arguments.source
    file_list = get_files(source_directory)
    cms_objects, unmoved = make_object_dirs(source_directory, file_list)
    make_object_bags(source_directory, cms_objects)
    clean_up(source_directory)
    print('Did not move this stuff: {}'.format(', '.join(unmoved)))


if __name__ == '__main__':
    main()
    exit(0)
