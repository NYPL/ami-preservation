#!/usr/bin/env python3

import os
import json
import shutil
import subprocess
import argparse
from datetime import datetime, timezone
import re
import bagit
from pymediainfo import MediaInfo
from pathlib import Path

def concatenate_files(file_list, output_file):
    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))
    list_path = os.path.join(os.path.dirname(output_file), 'file_list.txt')
    total_source_duration = 0  # Initialize the total duration of source files

    with open(list_path, 'w') as file_list_file:
        for file in sorted(file_list):
            file_list_file.write(f"file '{file}'\n")
            media_info = MediaInfo.parse(file)
            # Assuming the duration is provided in milliseconds
            total_source_duration += media_info.general_tracks[0].duration

    concat_command = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_path, '-c:a', 'flac', output_file]
    subprocess.run(concat_command, check=True)
    os.remove(list_path)
    print(f'Concatenated file created at {output_file}')

    # Now get the duration of the concatenated file
    media_info_concat = MediaInfo.parse(output_file)
    concat_file_duration = media_info_concat.general_tracks[0].duration

    # Check if the durations match
    if abs(total_source_duration - concat_file_duration) > 1000:  # 1000 ms tolerance for any rounding errors
        print("Warning: Duration mismatch detected in concatenated file.")
    else:
        print("Duration check passed.")


def update_json_metadata(json_file, new_flac_file):
    with open(json_file, 'r', encoding='utf-8-sig') as f:
        metadata = json.load(f)

    media_info = MediaInfo.parse(new_flac_file)
    track = media_info.tracks[0]

    # Extract date using regex from file_last_modification_date
    pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
    date_created = pattern.search(track.file_last_modification_date).group(0) if pattern.search(track.file_last_modification_date) else None

    metadata['asset']['referenceFilename'] = os.path.basename(new_flac_file)
    metadata['technical']['filename'] = os.path.splitext(os.path.basename(new_flac_file))[0]
    metadata['technical']['fileSize']['measure'] = track.file_size
    metadata['technical']['durationHuman'] = datetime.fromtimestamp(track.duration/1000, tz=timezone.utc).strftime('%H:%M:%S')
    metadata['technical']['durationMilli']['measure'] = track.duration
    metadata['technical']['dateCreated'] = date_created

    signal_notes = metadata['technical'].get('signalNotes', '')
    new_signal_notes = re.sub(r'Program Split Due to File Size Limitation;?\s*', 'Program Split into Parts Due to File Size Limitation, Concatenated upon Delivery by NYPL; ', signal_notes)
    metadata['technical']['signalNotes'] = new_signal_notes.strip()

    with open(json_file, 'w') as f:
        json.dump(metadata, f, indent=4)
    print(f'Updated JSON metadata at {json_file}')

def process_directory(input_dir, output_dir):
    bag_base_dir = os.path.join(output_dir, os.path.basename(input_dir))
    em_dir = os.path.join(bag_base_dir, 'EditMasters')
    pm_dir = os.path.join(bag_base_dir, 'PreservationMasters')
    images_dir = os.path.join(bag_base_dir, 'Images')  # Path for images directory in the destination

    # Ensure all necessary directories are created
    for dir_path in [em_dir, pm_dir, images_dir]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    for root, dirs, files in os.walk(input_dir):
        flac_files = [os.path.join(root, f) for f in files if f.endswith('.flac')]
        json_files = [os.path.join(root, f) for f in files if f.endswith('.json')]
        image_files = [os.path.join(root, f) for f in files if f.endswith('.JPG')]  # Collect image files

        if 'EditMasters' in root or 'PreservationMasters' in root:
            part_type = 'pm' if 'PreservationMasters' in root else 'em'
            target_dir = pm_dir if part_type == 'pm' else em_dir

            if flac_files:
                parts = os.path.basename(flac_files[0]).split('_')
                version_part = parts[2]
                version = version_part[:-3]
                base_filename = '_'.join(parts[:2] + [version]) + f'_{part_type}.flac'
                output_flac = os.path.join(target_dir, base_filename)
                concatenate_files(flac_files, output_flac)

                if json_files:
                    output_json = os.path.join(target_dir, base_filename.replace('.flac', '.json'))
                    shutil.copy(json_files[0], output_json)
                    update_json_metadata(output_json, output_flac)

        # Handle copying of image files
        if 'Images' in root:
            for image_file in image_files:
                shutil.copy(image_file, images_dir)
                print(f"Copied image {os.path.basename(image_file)} to {images_dir}")


def create_bag(bag_directory):
    """ Creates a BagIt bag for the given directory. """
    bag_directory = Path(bag_directory)
    if bag_directory.is_dir():
        bag = bagit.make_bag(str(bag_directory), checksums=['md5'])
        print(f"Created BagIt bag for {bag_directory}")

def main():
    parser = argparse.ArgumentParser(description='Process and repackage audio files into BagIt format.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-b', '--bag', help='Path to a single bag directory to process', type=str)
    group.add_argument('-d', '--directory', help='Path to a directory containing multiple bags to process', type=str)
    parser.add_argument('-o', '--output', help='Output directory for concatenated and re-bagged files', required=True)

    args = parser.parse_args()

    if not os.path.exists(args.output):
        os.makedirs(args.output)

    if args.bag:
        process_directory(args.bag, args.output)
        # Call create_bag at the bag base directory level
        create_bag(os.path.join(args.output, os.path.basename(args.bag)))
    elif args.directory:
        # Retrieve all subdirectories, sort them, and process each one
        subdirs = sorted([subdir for subdir in Path(args.directory).iterdir() if subdir.is_dir()])
        for subdir in subdirs:
            process_directory(str(subdir), args.output)
            # Call create_bag at the bag base directory level
            create_bag(os.path.join(args.output, os.path.basename(str(subdir))))

if __name__ == "__main__":
    main()