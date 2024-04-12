#!/usr/bin/env python3

import argparse
import json
import logging
import subprocess
import os
from pathlib import Path
import re
from fmrest import Server

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
    parser = argparse.ArgumentParser(description="Create NYPL JSON Files using media files and FileMaker database")
    parser.add_argument('-u', '--username', required=True, help='Username for FileMaker database')
    parser.add_argument('-p', '--password', required=True, help='Password for FileMaker database')
    parser.add_argument('-m', '--media', required=True, help='Path to directory of media files')
    parser.add_argument('-d', '--digitizer', choices=['Media Preserve', 'NYPL', 'Memnon'], required=False, help='Name of the digitizer')
    parser.add_argument('-o', '--output', required=True, help='Path to destination for JSON files')
    parser.add_argument('-c', '--config', required=True, help='Path to config file')
    return parser.parse_args()

def connect_to_filemaker(server, username, password, database, layout):
    url = f"https://{server}"
    api_version = 'v1'
    fms = Server(url, database=database, layout=layout, user=username, password=password, verify_ssl=True, api_version=api_version)
    try:
        fms.login()
        logger.info("Successfully connected to the FileMaker database.")
        return fms
    except Exception as e:
        logger.error(f"Failed to connect to Filemaker server: {e}")
        return None


def load_config(config_file):
    with open(config_file) as f:
        config = json.load(f)
    return config


valid_extensions = {".mov", ".wav", ".flac", ".mkv", ".dv", ".mp4", ".iso"}


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


def get_bibliographic_data(fms, cms_id):
    query = [{"ref_ami_id": cms_id}]
    try:
        found_records = fms.find(query)
        if found_records:
            record = found_records[0]
            vernacular_division_code = getattr(record, 'division', '')  # Assuming 'division' is the vernacular code
            division_code = map_division_code(vernacular_division_code)
            biblio_data = {
                'barcode': str(getattr(record, 'id_barcode', '')),
                'cmsItemID': cms_id,
                'divisionCode': division_code,
                'vernacularDivisionCode': vernacular_division_code,
                'primaryID': cms_id,
                'title': getattr(record, 'id_label_text', ''),
                'format_1': getattr(record, 'format_1', ''),
                'format_2': getattr(record, 'format_2', ''),
                'format_3': getattr(record, 'format_3', '')
            }
            return biblio_data
        else:
            logger.warning(f"No records found for CMS ID {cms_id}.")
            return None
    except Exception as e:
        logger.error(f"An error occurred while retrieving data for CMS ID {cms_id}: {e}")
        return None


def determine_type_format(biblio_data):
    format_lower = biblio_data['format_1'].lower()
    if format_lower in ['video', 'sound recording']:
        # Use format_3 for video and sound recordings and apply format_fixes
        return biblio_data['format_3'], True, None  # Adding None as the third return value for direct_type
    elif format_lower == 'film':
        # For films, directly use 'film' as type and format_2 as format, without applying format_fixes
        return biblio_data['format_2'], False, 'film'  # Returning 'film' explicitly in lowercase
    else:
        return None, False, None  # Ensure three values are returned for any other unexpected case


def map_division_code(vernacular_code):
    mapping = {
        'SCL': 'scb',
        'DAN': 'myd',
        'RHA': 'myh',
        'MUS': 'mym',
        'TOFT': 'myt',
        'THE': 'myt',
        'MSS': 'mao',
        'GRD': 'grd',
        'NYPLarch': 'axv',
        'MUL': 'mul',
        'BRG': 'mae',
        'JWS': 'maf',
        'LPA': 'myr'
    }
    return mapping.get(vernacular_code, '')  # Return empty string if no match


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
    
    format_name, apply_format_fixes, direct_type = determine_type_format(media_data['bibliographic'])
    object_type = direct_type if direct_type else ''  # Use direct_type if available

    if apply_format_fixes and format_name:
        for type, formats in config['format_fixes'].items():
            if format_name in formats:
                object_type = type
                break

    filename = media_data['filename']
    basename = filename.rsplit('.', 1)[0]  # filename without extension
    json_dir = Path(args.output)

    volume_match = re.search(r"_v(\d+)", filename)
    volume_number = int(volume_match.group(1)) if volume_match else 1

    date_created = media_data['media_info']['general'].get('File_Modified_Date', '')
    match = re.search(r"\d{4}-\d{2}-\d{2}", date_created)
    date_created = match.group() if match else ''

    # Initialize bibliographic data
    biblio_data = {
        'barcode': media_data['bibliographic'].get('barcode', ''),
        'cmsCollectionID': media_data['bibliographic'].get('cmsCollectionID', ''),
        'cmsItemID': media_data['cms_id'],
        'divisionCode': media_data['bibliographic'].get('divisionCode', ''),
        'primaryID': media_data['cms_id'],
        'title': media_data['bibliographic'].get('title', ''),
        'vernacularDivisionCode': media_data['bibliographic'].get('vernacularDivisionCode', ''),
    }
    
    # Add classmark only if not empty
    classmark = media_data['bibliographic'].get('classmark', '')
    if classmark:
        biblio_data['classmark'] = classmark

    nested_json = {
        'asset': {
            'fileRole': media_data['role'],
            'referenceFilename': media_data['filename'],  # filename includes the extension
            'schemaVersion': 'x.0'
        },
        'bibliographic': biblio_data,
        'source': {
            'object': {
                'format': format_name,
                'type': object_type,
                'volumeNumber': volume_number
            }
        },
        'technical': {
            # Populate technical details as needed
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

    json_filepath = json_dir / f"{basename}.json"  # Use basename for the output JSON filename
    try:
        with open(json_filepath, 'w') as f:
            json.dump(nested_json, f, indent=4)
        logger.info(f"JSON file created successfully: {json_filepath}")
    except OSError as e:
        logger.error(f"Error creating JSON file for {basename}: {e}")



def process_media_files(args, fms, media_list, config):
    for filepath in media_list:
        media_data = parse_media_file(filepath)
        if media_data:
            cms_id = media_data['cms_id']
            bibliographic_data = get_bibliographic_data(fms, cms_id)
            if bibliographic_data:
                media_data['bibliographic'] = bibliographic_data
                logger.info(f"Now making JSON for {media_data['filename']} file")
                create_new_json(args, media_data, config)
            else:
                logger.warning(f"No bibliographic data found for SPEC AMI ID {cms_id}. File will not be processed.")



def main():
    global logger
    logger = setup_logging()
    args = get_args()
    config = load_config(args.config)

    # Setup FileMaker connection
    server = os.getenv('FM_SERVER')
    database = os.getenv('FM_DATABASE')
    layout = os.getenv('FM_LAYOUT')
    if not all([server, database, layout]):
        logger.error("Server, database, and layout need to be set as environment variables.")
        return

    fms = connect_to_filemaker(server, args.username, args.password, database, layout)
    if not fms:
        return

    media_list = get_media_files(args)
    process_media_files(args, fms, media_list, config)

    fms.logout()

if __name__ == '__main__':
    main()
