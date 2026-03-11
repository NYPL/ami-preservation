#!/usr/bin/env python3

import argparse
from pathlib import Path
import re
import shutil

def get_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Undo object-level packaging and bagging')
    parser.add_argument('-d', '--directory',
                        help='path to the directory of object bags', required=True)
    args = parser.parse_args()
    return args


def get_directory(args):
    """Get source directory from arguments."""
    source_directory = Path(args.directory)
    if not source_directory.exists():
        exit('please retry with a valid directory of media files')

    return source_directory


def move_files_to_subfolders(source_directory):
    """Move files to their respective subfolders based on their file extensions."""

    file_mappings = [
        (('.mkv', 'pm.json', '.dv', '.framemd5', '.gz', 'graphs.jpeg', 'timecodes.txt', 'pm.wav', 'pm.flac', '.iso', 'pm.cue', '.scc'), 'PreservationMasters'),
        (('.mp4', 'sc.json'), 'ServiceCopies'),
        (('.mov', 'mz.json'), 'Mezzanines'),
        (('em.wav', 'em.json', 'em.flac'), 'EditMasters'),
        (('.jpg', '.tif'), 'Images'),
    ]

    created_folders = {}

    for filepath in source_directory.glob('**/*'):
        if filepath.is_file():
            for extensions, folder_name in file_mappings:
                if filepath.suffix[1:] in extensions or any(name in filepath.name for name in extensions):
                    dest_folder = source_directory / folder_name

                    # Create folder only if not already created
                    if folder_name not in created_folders:
                        dest_folder.mkdir(exist_ok=True)
                        created_folders[folder_name] = dest_folder

                    print(f'Moving: {filepath.name}')
                    try:
                        shutil.move(str(filepath), str(dest_folder / filepath.name))
                    except Exception as e:
                        print(f'Error moving file {filepath.name}: {e}')
                    break

    return file_mappings


def clean_up(source_directory):
    """Remove empty directories and BagIt residue files recursively."""
    # 1. Clean up known BagIt files that prevent directory deletion
    bagit_files = {'bagit.txt', 'bag-info.txt', 'fetch.txt'}
    for filepath in source_directory.rglob('*'):
        if filepath.is_file():
            if filepath.name in bagit_files or filepath.name.startswith('manifest-') or filepath.name.startswith('tagmanifest-'):
                try:
                    filepath.unlink()
                    print(f'Deleted BagIt residue: {filepath.name}')
                except Exception as e:
                    print(f'Could not delete file {filepath.name}: {e}')

    # 2. Walk the tree bottom-up to safely delete nested empty directories
    for directory in sorted(source_directory.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if directory.is_dir():
            try:
                if not any(directory.iterdir()):
                    print(f'Deleting empty directory: {directory.name}')
                    directory.rmdir()
            except Exception as e:
                print(f'Could not delete directory {directory.name}: {e}')


def main():
    arguments = get_args()
    source = get_directory(arguments)
    file_mappings = move_files_to_subfolders(source)
    clean_up(source)

if __name__ == '__main__':
    main()
    exit(0)
