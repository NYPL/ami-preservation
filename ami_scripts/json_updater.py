#!/usr/bin/env python3

import argparse
import json
import logging
import subprocess
from pathlib import Path

def get_args():
    parser = argparse.ArgumentParser(description='Update JSON files in a directory')
    parser.add_argument('-s', '--source', help='Path to the source directory of JSON files', required=True)
    parser.add_argument('-m', '--mediainfo', help='Update MediaInfo information in JSON files', action='store_true')
    parser.add_argument('-k', '--key', help='Key to update in JSON files')
    args = parser.parse_args()
    return args


def get_media_files(source_directory):
    media_files = []
    json_files = []
    
    for item in source_directory.glob('**/*'):
        if item.is_file() and item.suffix in ('.flac', '.mp4', '.mkv', '.wav'):
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

        media_info = subprocess.run(
            [
                'mediainfo', '--Language=raw', '--Full',
                '--Output=JSON', media_file
            ],
            capture_output=True, text=True
        )

        media_info_data = json.loads(media_info.stdout)
        general_data = media_info_data['media']['track'][0]

        with open(json_file, "r") as jsonFile:
            data = json.load(jsonFile)

        data['asset']['referenceFilename'] = media_file.name
        data['technical']['filename'] = media_file.stem
        data['technical']['extension'] = media_file.suffix[1:]
        data['technical']['dateCreated'] = general_data.get('File_Modified_Date', '').split(' ')[0]
        data['technical']['fileFormat'] = general_data.get('Format', '')
        data['technical']['audioCodec'] = general_data.get('Audio_Codec_List', '')
        data['technical']['fileSize']['measure'] = int(general_data.get('FileSize', 0))
        data['technical']['durationMilli']['measure'] = int(float(general_data.get('Duration', 0)) * 1000)
        data['technical']['durationHuman'] = general_data.get('Duration_String3', '')

        with open(json_file, "w") as jsonFile:
            json.dump(data, jsonFile, indent=4)

    logging.info("Media information updated in all JSON files")


def get_nested_values(data, key, parent_keys=None):
    values = []

    if parent_keys is None:
        parent_keys = []

    def _get_nested_values(data, key, parent_keys):
        for k, v in data.items():
            if k == key:
                values.append((tuple(parent_keys), v))
            elif isinstance(v, dict):
                _get_nested_values(v, key, parent_keys + [k])

    _get_nested_values(data, key, parent_keys)
    return values


def update_nested_key(data, key, old_value, new_value):
    for k, v in data.items():
        if k == key and v == old_value:
            data[k] = new_value
        elif isinstance(v, dict):
            update_nested_key(v, key, old_value, new_value)


def update_key_in_json_files(source_directory, key):
    _, json_files = get_media_files(source_directory)

    if not json_files:
        logging.info("No JSON files found in the source directory")
        return

    new_value = input(f"Enter the new value for the key '{key}': ")

    for json_file in json_files:
        with open(json_file, "r") as jsonFile:
            data = json.load(jsonFile)

        values = get_nested_values(data, key)
        unique_values = list(set(values))

        if not unique_values:
            logging.warning(f"Key '{key}' not found in JSON file {json_file}")
            continue

        if len(unique_values) == 1:
            parent_keys, old_value = unique_values[0]
            update_nested_key(data, key, old_value, new_value)
        else:
            print(f"\nValues found for key '{key}' in JSON file {json_file}:")
            for i, (parent_keys, value) in enumerate(unique_values, start=1):
                parent_key_string = ' > '.join(parent_keys)
                print(f"{i}. {parent_key_string} > {key}: {value}")

            choice = int(input("Enter the number of the value you want to update (0 to skip): "))
            if choice == 0:
                continue

            old_value = unique_values[choice - 1][1]
            update_nested_key(data, key, old_value, new_value)

        with open(json_file, "w") as jsonFile:
            json.dump(data, jsonFile, indent=4)

    logging.info(f"Key '{key}' updated in selected JSON files")


def main():
    logging.basicConfig(level=logging.INFO)
    arguments = get_args()
    source_directory = Path(arguments.source)

    if arguments.mediainfo:
        process_media_files(source_directory)

    if arguments.key:
        update_key_in_json_files(source_directory, arguments.key)

if __name__ == '__main__':
    main()

