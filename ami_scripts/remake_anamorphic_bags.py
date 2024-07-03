#!/usr/bin/env python3

import argparse
import os
import subprocess
import json
import hashlib
import logging
from pathlib import Path
from pymediainfo import MediaInfo

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def is_bag(directory):
    return all(os.path.exists(os.path.join(directory, fname)) for fname in ['bag-info.txt', 'bagit.txt', 'manifest-md5.txt', 'tagmanifest-md5.txt'])

def make_anamorphic_scs(directory):
    modified_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('sc.mp4'):
                filepath = os.path.join(root, file)
                temp_filepath = filepath + ".temp.mp4"
                logging.info(f"Now re-transcoding this file: {filepath}")
                command = [
                    "ffmpeg",
                    "-i", filepath,
                    "-c:v", "libx264",
                    "-movflags", "faststart",
                    "-pix_fmt", "yuv420p",
                    "-b:v", "3500000",
                    "-bufsize", "1750000",
                    "-maxrate", "3500000",
                    "-vf", "setdar=16/9",
                    "-c:a", "copy",
                    temp_filepath
                ]
                subprocess.run(command)
                os.remove(filepath)
                os.rename(temp_filepath, filepath)
                modified_files.append(filepath)
    return modified_files

def modify_json(directory):
    modified_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('_sc.json'):
                filepath = os.path.join(root, file)
                media_file = file.replace("_sc.json", "_sc.mp4")
                media_file_path = os.path.join(root, media_file)
                media_info = MediaInfo.parse(media_file_path)
                general_tracks = [t for t in media_info.tracks if t.track_type == "General"]
                if general_tracks:
                    general_data = general_tracks[0].to_data()
                    date_created = general_data.get('file_last_modification_date', '')
                    logging.info(f"Updating JSON metadata for: {filepath}")
                    with open(filepath, 'r+') as json_file:
                        data = json.load(json_file)
                        data['technical']['dateCreated'] = date_created.split(' ')[0] if date_created else ''
                        data['technical']['fileSize']['measure'] = int(general_data.get('file_size', 0))
                        json_file.seek(0)
                        json.dump(data, json_file, indent=4)
                        json_file.truncate()
                modified_files.append(filepath)
    return modified_files

def calculate_file_checksum(file_path):
    logging.info(f"Calculating checksum for file: {file_path}")  # Confirm correct path
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def update_manifests(directory, modified_files):
    manifest_path = os.path.join(directory, 'manifest-md5.txt').strip()
    tag_manifest_path = os.path.join(directory, 'tagmanifest-md5.txt').strip()

    # Update manifest-md5.txt
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r') as file:
            lines = file.readlines()

        with open(manifest_path, 'w') as file:
            for line in lines:
                path, filename = line.strip().split(' ', 1)
                full_path = os.path.join(directory, filename.strip())  # Ensure no spaces
                if filename.strip() in modified_files:
                    logging.info(f"Updating checksum for: {full_path}")
                    new_checksum = calculate_file_checksum(full_path)
                    file.write(f"{new_checksum} {filename}\n")
                else:
                    file.write(line)

    # Update tagmanifest-md5.txt
    if os.path.exists(tag_manifest_path):
        with open(tag_manifest_path, 'r') as file:
            lines = file.readlines()

        with open(tag_manifest_path, 'w') as file:
            for line in lines:
                checksum, filename = line.strip().split(' ', 1)
                if 'manifest-md5.txt' in filename:
                    logging.info(f"Updating checksum for tag manifest: {manifest_path}")
                    new_checksum = calculate_file_checksum(manifest_path)
                    file.write(f"{new_checksum} {filename}\n")
                else:
                    file.write(line)

def update_tagmanifest(directory):
    tag_manifest_path = os.path.join(directory, 'tagmanifest-md5.txt')
    bag_info_path = os.path.join(directory, 'bag-info.txt')
    manifest_path = os.path.join(directory, 'manifest-md5.txt')

    if os.path.exists(tag_manifest_path):
        # Read existing tagmanifest entries
        with open(tag_manifest_path, 'r') as file:
            lines = file.readlines()

        # Write updates only for the manifest-md5.txt and bag-info.txt
        with open(tag_manifest_path, 'w') as file:
            for line in lines:
                path = line.strip().split(' ', 1)[1]
                if 'manifest-md5.txt' in path:
                    new_checksum = calculate_file_checksum(manifest_path)
                    file.write(f"{new_checksum} {path}\n")
                elif 'bag-info.txt' in path:
                    new_checksum = calculate_file_checksum(bag_info_path)
                    file.write(f"{new_checksum} {path}\n")
                else:
                    file.write(line)

        logging.info("tagmanifest-md5.txt updated successfully.")


def update_payload_oxum(directory):
    data_directory = Path(directory) / 'data'
    total_size = 0
    total_files = 0

    for file in data_directory.rglob('*'):
        if file.is_file():
            total_size += file.stat().st_size
            total_files += 1

    oxum = f'{total_size}.{total_files}'
    bag_info_path = Path(directory) / 'bag-info.txt'

    if bag_info_path.exists():
        with open(bag_info_path, 'r') as file:
            lines = file.readlines()

        with open(bag_info_path, 'w') as file:
            for line in lines:
                if line.startswith('Payload-Oxum'):
                    file.write(f'Payload-Oxum: {oxum}\n')
                else:
                    file.write(line)
        logging.info(f"Updated Payload-Oxum to {oxum} in bag-info.txt")

def main():
    parser = argparse.ArgumentParser(description='Process BagIt packages for anamorphic service copies.')
    parser.add_argument('-d', '--directory', required=True, help='Directory containing BagIt packages')
    args = parser.parse_args()

    for bag in os.listdir(args.directory):
        bag_path = os.path.join(args.directory, bag)
        if os.path.isdir(bag_path) and is_bag(bag_path):
            logging.info(f"Now processing this bag: {bag_path}")
            servicecopy_dir = os.path.join(bag_path, 'data', 'ServiceCopies')
            modified_files = make_anamorphic_scs(servicecopy_dir) + modify_json(os.path.join(bag_path, 'data'))
            relative_modified_files = [os.path.relpath(f, bag_path).strip() for f in modified_files]
            update_manifests(bag_path, relative_modified_files)
            update_payload_oxum(bag_path)
            update_tagmanifest(bag_path)

if __name__ == "__main__":
    main()
