#!/usr/bin/env python3

import os
import sys
import argparse
import subprocess
import hashlib
from pathlib import Path
import shutil

def calculate_checksum(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def compare_checksums(src_dir, dest_dir):
    src_files = sorted(Path(src_dir).rglob('*'))
    dest_files = sorted(Path(dest_dir).rglob('*'))

    for src_file, dest_file in zip(src_files, dest_files):
        if src_file.is_file() and dest_file.is_file():
            src_checksum = calculate_checksum(src_file)
            dest_checksum = calculate_checksum(dest_file)

            if src_checksum != dest_checksum:
                return False
    return True


def move_files(temp_dest_dir, dest_dir):
    for item in os.listdir(temp_dest_dir):
        source_item = os.path.join(temp_dest_dir, item)
        dest_item = os.path.join(dest_dir, item)
        if os.path.isdir(source_item):
            shutil.move(source_item, dest_item)  # Change from copytree to move
        else:
            shutil.move(source_item, dest_item)  # Change from copy2 to move
    shutil.rmtree(temp_dest_dir)


def main():
    parser = argparse.ArgumentParser(description="Safely copy files using rsync and verify the copied files.")
    parser.add_argument('-s', '--source', required=True, help="Source directory")
    parser.add_argument('-d', '--destination', required=True, help="Destination directory")
    parser.add_argument('-c', '--checksum', action='store_true', help="Enable checksum comparison for file content")

    args = parser.parse_args()

    src_dir = args.source
    dest_dir = args.destination

    # Create a temporary subdirectory within the destination directory
    temp_dest_dir = os.path.join(dest_dir, "temp_rsync")
    os.makedirs(temp_dest_dir, exist_ok=True)

    # Copy the entire source directory using rsync with -rtv flags
    rsync_command = f'rsync -rtv --recursive --progress "{src_dir}" "{temp_dest_dir}"'
    subprocess.run(rsync_command, shell=True, check=True)

    # Check for differences using the 'diff' command
    print("Comparing source and temporary destination directories using 'diff' command...")
    copied_src_dir = os.path.join(temp_dest_dir, os.path.basename(src_dir))
    diff_command = f'diff -r "{src_dir}" "{copied_src_dir}"'
    diff_output = subprocess.run(diff_command, shell=True, text=True, stderr=subprocess.PIPE)

    if diff_output.returncode == 0:
        print("All files have been copied successfully and are identical.")
    else:
        print("Differences found between source and destination:")
        print(diff_output.stderr)

    # Check if the sizes of source and destination directories are the same
    src_size = sum(f.stat().st_size for f in Path(src_dir).rglob('*') if f.is_file())
    temp_dest_size = sum(f.stat().st_size for f in Path(temp_dest_dir).rglob('*') if f.is_file())

    if src_size == temp_dest_size:
        print("Source and temporary destination directories are the same size.")
    else:
        print("Source and temporary destination directories have different sizes:")
        print(f"Source: {src_size}")
        print(f"Temporary Destination: {temp_dest_size}")

    # Compare the number of files in source and temporary destination directories
    src_file_count = len([f for f in Path(src_dir).rglob('*') if f.is_file()])
    temp_dest_file_count = len([f for f in Path(temp_dest_dir).rglob('*') if f.is_file()])

    if src_file_count == temp_dest_file_count:
        print("Source and temporary destination directories have the same number of files.")
    else:
        print("Source and temporary destination directories have different number of files:")
        print(f"Source: {src_file_count}")
        print(f"Temporary Destination: {temp_dest_file_count}")

    # Compare checksums of files in source and temporary destination directories, if checksum comparison is enabled
    if args.checksum:
        if compare_checksums(src_dir, temp_dest_dir):
            print("Checksum comparison: All files have matching checksums.")
        else:
            print("Checksum comparison: Some files have different checksums.")

    validation_passed = True

    if args.checksum:
        if compare_checksums(src_dir, temp_dest_dir):
            print("Checksum comparison: All files have matching checksums.")
        else:
            print("Checksum comparison: Some files have different checksums.")
            validation_passed = False

    # If everything is okay, move the files from the temporary subdirectory to the actual destination directory
    if validation_passed:
        move_files(temp_dest_dir, dest_dir)
    else:
        print("Validation failed. Files will not be moved to the destination directory.")


if __name__ == "__main__":
    main()
