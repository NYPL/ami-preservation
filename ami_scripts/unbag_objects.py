#!/usr/bin/env python3

import argparse
from pathlib import Path
import re
import shutil

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

    file_mappings = [
        (('.mkv', 'pm.json', '.dv', '.framemd5', '.gz', 'graphs.jpeg', 'timecodes.txt', 'pm.wav', 'pm.flac', '.iso', 'pm.cue'), 'PreservationMasters'),
        (('.mp4', 'sc.json'), 'ServiceCopies'),
        (('em.wav', 'em.json', 'em.flac'), 'EditMasters'),
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


def clean_up(source_directory, file_mappings):
    """Remove empty directories and directories not containing files matching file_mappings."""
    for directory in source_directory.iterdir():
        cms = re.search(r'(\d{6})', directory.name)
        if cms and directory.is_dir():
            valid_files = False
            for filepath in directory.glob('*'):
                if filepath.is_file():
                    for extensions, folder_name in file_mappings:
                        if filepath.suffix[1:] in extensions or any(name in filepath.name for name in extensions):
                            valid_files = True
                            break
                if valid_files:
                    break

            if not valid_files:
                print(f'Deleting directory (no matching files): {directory.name}')
                shutil.rmtree(directory)
            else:
                print(f'Skipping directory with matching files: {directory.name}')



def main():
    arguments = get_args()
    source = get_directory(arguments)
    file_mappings = move_files_to_subfolders(source)
    clean_up(source, file_mappings)

if __name__ == '__main__':
    main()
    exit(0)
