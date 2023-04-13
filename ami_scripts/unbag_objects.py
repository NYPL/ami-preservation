#!/usr/bin/env python3

import argparse
from pathlib import Path
import re

def get_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Undo object-level packaging and bagging')
    parser.add_argument('-s', '--source',
                        help='path to the directory of object bags', required=True)
    args = parser.parse_args()
    return args

def get_directory(args):
    """Get source directory from arguments."""
    source_directory = Path(args.source)
    if not source_directory.exists():
        exit('please retry with a valid directory of media files')

    return source_directory

def move_files_to_subfolders(source_directory):
    """Move files to their respective subfolders based on their file extensions."""

    pm_path = source_directory / 'PreservationMasters'
    sc_path = source_directory / 'ServiceCopies'
    em_path = source_directory / 'EditMasters'

    pm_path.mkdir(exist_ok=True)
    sc_path.mkdir(exist_ok=True)
    em_path.mkdir(exist_ok=True)

    file_mappings = [
        (('.mkv', 'pm.json', '.dv', '.framemd5', '.gz', 'graphs.jpeg', 'timecodes.txt', 'pm.wav', 'pm.flac', '.iso', 'pm.cue'), pm_path),
        (('.mp4', 'sc.json'), sc_path),
        (('em.wav', 'em.json', 'em.flac'), em_path),
    ]

    for filepath in source_directory.glob('**/*'):
        if filepath.is_file():
            for extensions, dest_folder in file_mappings:
                if filepath.suffix in extensions:
                    print(f'Moving: {filepath.name}')
                    try:
                        filepath.rename(dest_folder / filepath.name)
                    except Exception as e:
                        print(f'Error moving file {filepath.name}: {e}')
                    break

def clean_up(source_directory):
    """Remove empty directories."""
    for directory in source_directory.iterdir():
        cms = re.search(r'(\d{6})', directory.name)
        if cms and directory.is_dir():
            if not any(directory.iterdir()):  # Check if the directory is empty
                print(f'Deleting empty directory: {directory.name}')
                directory.rmdir()
            else:
                print(f'Skipping non-empty directory: {directory.name}')

def main():
    arguments = get_args()
    source = get_directory(arguments)
    move_files_to_subfolders(source)
    clean_up(source)

if __name__ == '__main__':
    main()
    exit(0)
