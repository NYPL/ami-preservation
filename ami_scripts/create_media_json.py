#!/usr/bin/env python3

import argparse
import csv
import json
import logging
import subprocess
import os
from pathlib import Path
import re

def setup_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


def get_args():
    parser = argparse.ArgumentParser(description="Create NYPL JSON Files from SPEC Export and user-supplied directory of media files")
    parser.add_argument('-c', '--config', required=True, help='Path to config file')
    parser.add_argument('-s', '--source', help='path to SPEC CSV Export', required=False)
    parser.add_argument('-m', '--media', help='path to directory of media files', required=False)  # Modified here
    parser.add_argument('-d', '--digitizer', choices=['Media Preserve', 'NYPL', 'Memnon'], required=False, help='Name of the digitizer')
    parser.add_argument('-o', '--output', help='path to destination for JSON files', required=True)
    return parser.parse_args()



def load_config(config_file):
    with open(config_file) as f:
        config = json.load(f)
    return config


def load_csv(args):
    data_dict = {}
    if args.source:
        try:
            with open(args.source, 'r', encoding='utf-8', errors='ignore') as file:
                reader = csv.reader(file)
                headers = next(reader)
                for row in reader:
                    key = row[0]
                    values = row[1:]
                    data_dict[key] = dict(zip(headers[1:], values))
        except OSError as e:
            logger.error(f"Error loading CSV file: {e}")
    return data_dict

valid_extensions = {".mov", ".wav", ".flac", ".mkv", ".dv", ".mp4"}


def get_media_files(args):
    media_list = []
    if args.media:
        try:
            media_dir = os.scandir(args.media)
            for entry in media_dir:
                if entry.is_file() and entry.name.lower().endswith(tuple(valid_extensions)):
                    media_list.append(entry.path)
            media_list.sort()
        except OSError as e:
            logger.error(f"Error getting media files: {e}")
    if media_list:
        logger.info(f"Found these files: {', '.join(media_list)}")
    return media_list


def parse_media_file(filepath):
    try:
        filepath = Path(filepath)
        filename = filepath.name  # includes the extension
        extension = filepath.suffix[1:]
        basename = filepath.stem  # filename without the extension
        division, cmsID, _, role = basename.split('_')
        media_info = json.loads(subprocess.check_output(['mediainfo', '-f', '--Output=JSON', str(filepath)]).decode('utf-8'))

        # Prepare empty metadata dictionary
        media_metadata = {'general': {}, 'audio': {}, 'video': {}}

        # Loop over the tracks in the media_info object
        for track in media_info['media']['track']:
            if track['@type'].lower() in media_metadata:
                media_metadata[track['@type'].lower()].update(track)
        
        return {
            'filename': filename,
            'extension': extension,
            'division': division,
            'cms_id': cmsID,
            'role': role,
            'media_info': media_metadata,
            'file_size': filepath.stat().st_size
        }
    except (OSError, json.JSONDecodeError, subprocess.CalledProcessError, ValueError) as e:
        logger.error(f"Error parsing media file {filepath}: {e}")
        return None


def create_new_json(args, media_data, config):
    if media_data is None:
        return
    filename = media_data['filename']
    basename = filename.rsplit('.', 1)[0]  # filename without extension
    json_dir = Path(args.output)

    volume_match = re.search(r"_v(\d+)", filename)
    volume_number = int(volume_match.group(1)) if volume_match else 1

    date_created = media_data['media_info']['general'].get('File_Modified_Date', '')
    match = re.search(r"\d{4}-\d{2}-\d{2}", date_created)
    date_created = match.group() if match else ''

    # Determine object type based on object format and config
    format_name = media_data['bibliographic'].get('format.name', '')
    object_type = ''
    for type, formats in config['format_fixes'].items():
        if format_name in formats:
            object_type = type
            break

    nested_json = {
        'asset': {
            'fileRole': media_data['role'],
            'referenceFilename': media_data['filename'],  # filename includes the extension
            'schemaVersion': 'x.0'
        },
        'bibliographic': {
            'barcode': media_data['bibliographic'].get('barcode', ''),
            'classmark': media_data['bibliographic'].get('id.classmark', ''),
            'cmsCollectionID': media_data['bibliographic'].get('c#', ''),
            'cmsItemID': media_data['cms_id'],
            'divisionCode': media_data['division'],
            'primaryID': media_data['cms_id'],
            'title': media_data['bibliographic'].get('title', ''),
            'vernacularDivisionCode': media_data['bibliographic'].get('repository', '')
        },
        'source': {
            'object': {
                'format': format_name,
                'type': object_type,
                'volumeNumber': volume_number
            }
        },
        'technical': {
            'audioCodec': media_data['media_info']['audio'].get('Format', ''),
            'videoCodec': media_data['media_info']['video'].get('Format', None),
            'dateCreated': date_created,  # using the extracted date
            'durationHuman': media_data['media_info']['general'].get('Duration_String3', ''),  # use Duration_String3
            'durationMilli': {'measure': int(float(media_data['media_info']['general'].get('Duration', 0)) * 1000), 'unit': 'ms'},
            'extension': media_data['extension'],
            'fileFormat': media_data['media_info']['general'].get('Format', ''),
            'filename': media_data['filename'],
            'filesize': {'measure': media_data['file_size'], 'unit': 'B'}
        }
    }
    if args.digitizer:
        nested_json['digitizer'] = config['digitizers'][args.digitizer]

    # Remove any keys in the 'technical' dictionary that have a value of None
    nested_json['technical'] = {k: v for k, v in nested_json['technical'].items() if v is not None}

    json_filepath = json_dir / f"{basename}.json"  # Use basename for the output JSON filename
    try:
        with open(json_filepath, 'w') as f:
            json.dump(nested_json, f, indent=4)
    except OSError as e:
        logger.error(f"Error creating JSON file for {basename}: {e}")


def process_media_files(args, data_dict, media_list, config):
    for filepath in media_list:
        media_data = parse_media_file(filepath)
        if media_data is not None:
            cms_id = media_data['cms_id']
            if cms_id in data_dict:
                media_data['bibliographic'] = data_dict[cms_id]
                logger.info(f"Now making JSON for {media_data['filename']} file")
                create_new_json(args, media_data, config)
            else:
                logger.warning(f"{media_data['filename']} File not found in SPEC CSV Export (data dict)")


def main():
    global logger
    logger = setup_logging()
    arguments = get_args()
    config = load_config(arguments.config)
    csv_data = load_csv(arguments)
    media_list = get_media_files(arguments)
    process_media_files(arguments, csv_data, media_list, config)

if __name__ == '__main__':
    main()