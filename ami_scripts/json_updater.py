#!/usr/bin/env python3

import argparse
import json
import logging
from pathlib import Path
import re
from pymediainfo import MediaInfo
import hashlib
import os

def get_args():
    parser = argparse.ArgumentParser(description='Update JSON files in a directory')
    parser.add_argument('-s', '--source', help='Path to the source directory of JSON files', required=True)
    parser.add_argument('-m', '--mediainfo', help='Update MediaInfo information in JSON files', action='store_true')
    parser.add_argument('-k', '--key', help='Key to update in JSON files')
    parser.add_argument('-c', '--checksum', action='store_true', help='Update checksums and payload oxum for BagIt bag')
    args = parser.parse_args()
    return args


def remove_unwanted_files(source_directory):
    unwanted_files = list(source_directory.rglob('.DS_Store')) + list(source_directory.rglob('._*'))
    for file in unwanted_files:
        try:
            file.unlink()
            logging.info(f"Removed unwanted file: {file}")
        except Exception as e:
            logging.error(f"Failed to remove {file}: {e}")


def get_media_files(source_directory):
    media_files = []
    json_files = []
    
    for item in source_directory.glob('**/*'):
        if item.is_file() and item.suffix in ('.flac', '.mp4', '.mkv', '.wav', '.iso', '.mov'):
            media_files.append(item)
        elif item.is_file() and item.suffix == '.json':
            json_files.append(item)
    
    return media_files, json_files


def process_media_files(source_directory):
    file_list, json_list = get_media_files(source_directory)
    media_info_dict = {}

    for media_file in file_list:
        media_info_dict[media_file.stem] = media_file

    for json_file in json_list:
        media_file = media_info_dict.get(json_file.stem)

        if media_file is None:
            logging.warning(f"No media file found for JSON file {json_file}")
            continue

        media_info = MediaInfo.parse(media_file)
        general_tracks = [t for t in media_info.tracks if t.track_type == "General"]
        if general_tracks:
            general_data = general_tracks[0].to_data()
        else:
            logging.warning(f"No general track found for media file {media_file}")
            continue

        with open(json_file, "r", encoding="utf-8-sig") as jsonFile:
            data = json.load(jsonFile)

        data['asset']['referenceFilename'] = media_file.name
        data['technical']['filename'] = media_file.stem
        data['technical']['extension'] = media_file.suffix[1:]

        file_role = extract_file_role(media_file.stem)
        if file_role:
            data['asset']['fileRole'] = file_role

        date_created = general_data.get('file_last_modification_date', '')
        date_pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
        match = date_pattern.search(date_created)
        data['technical']['dateCreated'] = match.group(0) if match else ''
        
        data['technical']['fileSize']['measure'] = int(general_data.get('file_size', 0))
        data['technical']['fileFormat'] = general_data.get('format', '')
        
        # Handling the duration data
        duration = general_data.get('duration')
        if duration is not None:
            data['technical']['durationMilli'] = {'measure': int(duration), 'unit': 'ms'}

        # Simplify audio codec information
        audio_codec = general_data.get('audio_codecs', '')
        if audio_codec:
            # Split on '/' and strip whitespace, then take the unique set to avoid duplicates
            unique_codecs = set(code.strip() for code in audio_codec.split('/'))
            simplified_codec = ' / '.join(unique_codecs)  # Join unique codec names with '/'
            data['technical']['audioCodec'] = simplified_codec

        # Video codec and duration in human-readable form
        video_codec = general_data.get('codecs_video', '')
        if video_codec:
            data['technical']['videoCodec'] = video_codec

        other_duration = general_data.get('other_duration', [])
        if len(other_duration) > 3:
            data['technical']['durationHuman'] = other_duration[3]

        with open(json_file, "w", encoding="utf-8-sig") as jsonFile:
            json.dump(data, jsonFile, indent=4)

    logging.info("Media information updated in all JSON files")


def get_nested_values(data, path):
    """Retrieve value from a nested dictionary using a path (dot-separated keys)."""
    keys = path.split('.')
    for key in keys[:-1]:
        data = data.get(key, {})
    return data.get(keys[-1], None), data, keys[-1]  # Return the value, parent dict, and last key


def update_nested_key(parent_data, last_key, new_value):
    """Update a value in a nested dictionary based on the last key in the path."""
    parent_data[last_key] = new_value


def update_key_in_json_files(source_directory, path):
    _, json_files = get_media_files(source_directory)

    if not json_files:
        logging.info("No JSON files found in the source directory")
        return

    new_value = input(f"Enter the new value for the key '{path}': ")

    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8-sig") as jsonFile:
            data = json.load(jsonFile)

        old_value, parent_data, last_key = get_nested_values(data, path)
        if old_value is None:
            logging.warning(f"Key '{path}' not found in JSON file {json_file}")
            continue

        update_nested_key(parent_data, last_key, new_value)

        with open(json_file, "w", encoding="utf-8-sig") as jsonFile:
            json.dump(data, jsonFile, indent=4)

    logging.info(f"Key '{path}' updated in selected JSON files")


def extract_file_role(filename):
    # Extracting the part after the last underscore and before the extension
    parts = filename.rsplit('_', 1)
    if len(parts) > 1:
        role_with_extension = parts[-1]
        role = role_with_extension.split('.')[0]
        return role
    return ''


def update_json_checksums(source_directory):
    manifest_path = source_directory / 'manifest-md5.txt'
    if not manifest_path.exists():
        logging.error("Manifest file not found.")
        return

    # Read existing checksums into a dictionary
    existing_checksums = {}
    with open(manifest_path, "r") as manifest:
        for line in manifest:
            if line.strip():
                hash_sum, file_name = line.strip().split(maxsplit=1)
                existing_checksums[file_name] = hash_sum

    # Update checksums for .json files, keeping relative paths
    json_files = list(source_directory.glob('data/**/*.json'))  # Focus only on JSON files under 'data/'
    for json_file in json_files:
        with open(json_file, "rb") as file:
            file_data = file.read()
            checksum = hashlib.md5(file_data).hexdigest()
        relative_path = json_file.relative_to(source_directory)  # Get relative path to file from source directory
        existing_checksums[str(relative_path)] = checksum  # Use relative path in the manifest

    # Write all checksums back to the manifest, maintaining path structure
    with open(manifest_path, 'w') as manifest:
        for file_name, hash_sum in sorted(existing_checksums.items()):  # Sort to maintain consistent order
            manifest.write(f'{hash_sum} {file_name}\n')

    logging.info("Updated JSON checksums in manifest-md5.txt")



def update_payload_oxum(source_directory):
    data_directory = source_directory / 'data'
    if not data_directory.exists():
        logging.error("Data directory does not exist in the bag.")
        return

    total_size = 0
    total_files = 0

    # Ensure only payload files in 'data' directory are counted
    for file in data_directory.rglob('*'):
        if file.is_file():
            total_size += file.stat().st_size
            total_files += 1

    oxum = f'{total_size}.{total_files}'
    bag_info_path = source_directory / 'bag-info.txt'
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
    else:
        logging.error("bag-info.txt not found.")


def calculate_file_checksum(file_path):
    """Utility function to calculate MD5 checksum for a given file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def update_tagmanifest_checksums(source_directory):
    """Update checksums in tagmanifest-md5.txt for bag-info.txt and manifest-md5.txt."""
    tagmanifest_path = source_directory / 'tagmanifest-md5.txt'
    if not tagmanifest_path.exists():
        logging.error("Tagmanifest file not found.")
        return

    # Read existing checksums into a dictionary
    checksums = {}
    with open(tagmanifest_path, "r") as file:
        for line in file:
            parts = line.strip().split(' ', 1)
            if len(parts) == 2:
                checksums[parts[1]] = parts[0]

    # Update checksums for bag-info.txt and manifest-md5.txt
    for filename in ['bag-info.txt', 'manifest-md5.txt']:
        file_path = source_directory / filename
        if file_path.exists():
            checksums[filename] = calculate_file_checksum(file_path)

    # Write updated checksums back to tagmanifest-md5.txt
    with open(tagmanifest_path, 'w') as file:
        for filename, checksum in checksums.items():
            file.write(f'{checksum} {filename}\n')

    logging.info("Updated tagmanifest-md5.txt with new checksums.")


def main():
    logging.basicConfig(level=logging.INFO)
    arguments = get_args()
    source_directory = Path(arguments.source)

    # Remove unwanted hidden files first
    remove_unwanted_files(source_directory)

    if arguments.mediainfo:
        process_media_files(source_directory)

    if arguments.key:
        update_key_in_json_files(source_directory, arguments.key)

    if arguments.checksum:
        update_json_checksums(source_directory)
        update_payload_oxum(source_directory)
        update_tagmanifest_checksums(source_directory) 
        

if __name__ == '__main__':
    main()
