#!/usr/bin/env python3

import argparse
import os
import subprocess
import glob
import shutil
import re

def get_args():
    parser = argparse.ArgumentParser(description='Undo object-level packaging and bagging')
    parser.add_argument('-s', '--source',
                        help = 'path to the directory of object bags', required=True)
    args = parser.parse_args()
    return args

def get_directory(args):
    try:
        test_directory = os.listdir(args.source)
    except OSError:
        exit('please retry with a valid directory of media files')
    source_directory = args.source

    return source_directory

def get_file_list(source_directory):

    pm_path = os.path.join(source_directory, 'PreservationMasters')
    sc_path = os.path.join(source_directory, 'ServiceCopies')
    em_path = os.path.join(source_directory, 'EditMasters')

    if not os.path.exists(pm_path):
        os.makedirs(pm_path)
    if not os.path.exists(sc_path):
        os.makedirs(sc_path)
    if not os.path.exists(em_path):
        os.makedirs(em_path)

    for root, dirs, files in os.walk(source_directory):
        for file in files:
            sourcepath = os.path.join(root, file)
            if file.endswith(('.mkv', 'pm.json', '.dv', '.framemd5', '.gz', 'graphs.jpeg', 'timecodes.txt', 'pm.wav', 'pm.flac', '.iso')):
                destpath = os.path.join(pm_path, file)
                print('Moving: {}'.format(file))
                shutil.move(sourcepath, destpath)
            elif file.endswith(('.mp4', 'sc.json')):
                destpath = os.path.join(sc_path, file)
                print('Moving: {}'.format(file))
                shutil.move(sourcepath, destpath)
            elif file.endswith(('em.wav', 'em.json', 'em.flac')):
                destpath = os.path.join(em_path, file)
                print('Moving: {}'.format(file))
                shutil.move(sourcepath, destpath)

def clean_up(source_directory):
    cms_list = []
    for directory in os.listdir(source_directory):
        cms = re.search(r'(\d{6})', directory)
        if cms:
            dir_path = os.path.join(source_directory, cms.group(1))
            print('Deleting empty directory: {}'.format(directory))
            shutil.rmtree(dir_path)

def main():
    arguments = get_args()
    source = get_directory(arguments)
    list_of_files = get_file_list(source)
    clean_up(source)

if __name__ == '__main__':
    main()
    exit(0)
