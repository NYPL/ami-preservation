#!/usr/bin/env python3

import argparse
from pathlib import Path
import bagit
import re
import shutil


def get_args():
    parser = argparse.ArgumentParser(description='Move files into object dirs and bag')
    parser.add_argument('-s', '--source',
                        help='path to the source directory files', required=True)
    args = parser.parse_args()
    return args


def get_files(source_directory):
    return [path.relative_to(source_directory) for path in source_directory.glob('**/*') if path.is_file()]


def make_object_dirs(source_directory, file_list):
    cms_ids = set()
    unmoved = []
    tags = []

    for file_path in file_list:
        try:
            cms_id = re.search(r'_(\d{6})_', str(file_path)).group(1)
            cms_ids.add(cms_id)
        except AttributeError:
            print(f'Warning: Unrecognized file: {file_path}')
            unmoved.append(file_path)
            continue

        old_file_path = source_directory / file_path
        new_file_path = source_directory / cms_id / file_path
        new_file_path.parent.mkdir(parents=True, exist_ok=True)

        if old_file_path.suffix in ('.mkv', '.json', '.mp4', '.dv', '.flac', '.iso', '.cue', '.mov', '.jpg'):
            shutil.move(str(old_file_path), str(new_file_path))
        else:
            tags.append(old_file_path)
        print(f'Moving file: {cms_id}')

    return cms_ids, unmoved, tags


def make_object_bags(source_directory, cms_objects):
    for cms_id in cms_objects:
        bag_path = source_directory / cms_id
        bagit.make_bag(str(bag_path), checksums=['md5'])
        print(f'Bagging object: {cms_id}')


def move_tag_files(source_directory, tags):
    for tag_file in tags:
        cms_id = re.search(r'_(\d{6})_', str(tag_file)).group(1)
        object_bag = source_directory / cms_id

        if not object_bag.exists():
            print(f'Warning: No bag found for object {cms_id}')
            continue

        else:
            tag_dir = object_bag / 'tags'
            tag_dir.mkdir(exist_ok=True)
            shutil.move(str(tag_file), str(tag_dir))

            bag = bagit.Bag(str(object_bag))
            bag.save(manifests=True, tagmanifests=True)


def clean_up(source_directory):
    for directory in source_directory.iterdir():
        if directory.is_dir() and not any(directory.iterdir()):
            print(f'Deleting empty directory: {directory}')
            directory.rmdir()


def main():
    arguments = get_args()
    source_directory = Path(arguments.source)
    file_list = get_files(source_directory)
    cms_objects, unmoved, tags = make_object_dirs(source_directory, file_list)
    make_object_bags(source_directory, cms_objects)
    move_tag_files(source_directory, tags)
    clean_up(source_directory)
    print(f'Did not move this stuff: {", ".join(map(str, unmoved))}')


if __name__ == '__main__':
    main()
    exit(0)
