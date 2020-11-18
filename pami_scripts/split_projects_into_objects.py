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
    # list to report object_dirs created, untouched files, and tag files to move after bagging
    cms_ids = set()
    unmoved = []
    tags = []

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
        if old_file_path.endswith(('mkv', 'json', 'mp4', 'dv', 'flac')):
            shutil.move(old_file_path, new_file_path)
        else:
            tags.append(old_file_path)
        print('Moving: {}'.format(cms_id))

    return cms_ids, unmoved, tags


def make_object_bags(source_directory, cms_objects):
    for cms_id in cms_objects:
        bagit.make_bag(os.path.join(source_directory, cms_id), checksums=['md5'])
        print('Bagging: {}'.format(cms_id))


def move_tag_files(source_directory, tags):
    # move tag files after bagging into a tags folder
    # then update the tag manifest
    for tag_file in tags:
        cms_id = re.search(r'_(\d{6})_', tag_file).group(1)
        object_bag = os.path.join(source_directory, cms_id)

        # tag file for object that didn't get bagged
        if not os.path.exists(object_bag):
            print('ummm, no bag for {}'.format(cms_id))
            continue

        else:
            tag_dir = os.path.join(object_bag, 'tags')
            os.makedirs(tag_dir)
            shutil.move(tag_file, tag_dir)

            # update the tag manifest,
            # messy but takes advantage of bagit setup
            cur_dir = os.pwd()
            os.chdir(object_bag)
            bagit._make_tagmanifest_file("md5", object_bag)
            os.chdir(cur_dir)


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
    cms_objects, unmoved, tags = make_object_dirs(source_directory, file_list)
    move_tag_files(source_directory, tags)
    make_object_bags(cms_objects)
    clean_up(source_directory)
    print('Did not move this stuff: {}'.format(', '.join(unmoved)))


if __name__ == '__main__':
    main()
    exit(0)
