#!/usr/bin/env python3

import argparse
import csv
import logging
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from pprint import pprint
from pymediainfo import MediaInfo

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

video_extensions = {'.mkv', '.mov', '.mp4', '.dv', '.iso'}
audio_extensions = {'.wav', '.flac'}

def make_parser():
    parser = argparse.ArgumentParser(description="Pull MediaInfo from a bunch of video or audio files")
    parser.add_argument("-d", "--directory",
                        help="path to folder full of media files",
                        required=False)
    parser.add_argument("-f", "--file",
                        help="path to folder full of media files",
                        required=False)
    parser.add_argument("-o", "--output",
                        help="path to save csv",
                        required=True)
    parser.add_argument("-v", "--vendor", action='store_true', 
                        help="process as BagIt with sidecar JSON metadata")

    return parser

def is_bag(directory):
    required_files = {'bag-info.txt', 'bagit.txt', 'manifest-md5.txt', 'tagmanifest-md5.txt'}
    return required_files <= {file.name for file in directory.iterdir() if file.is_file()}

def process_bags(top_directory):
    bags = []
    for directory in top_directory.iterdir():
        if directory.is_dir() and is_bag(directory):
            bags.append(directory)
            logging.info(f"Identified BagIt bag: {directory}")
    return bags

def process_directory(bag_directory, process_json=False):
    valid_extensions = video_extensions.union(audio_extensions)
    media_files = []
    data_directory = bag_directory / "data"
    if data_directory.exists():
        for path in data_directory.rglob('*'):
            if path.is_file() and path.suffix.lower() in valid_extensions:
                if path.name.startswith("._"):
                    logging.info(f"Skipping hidden Mac file: {path}")
                else:
                    media_files.append(path)
                    logging.info(f"Adding file to processing list: {path}")
    return media_files

def read_json_sidecar(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
        logging.info(f"Reading JSON sidecar file: {json_path}")
        bib = data.get('bibliographic', {})
        src = data.get('source', {}).get('object', {})
        return {
            'collectionID': bib.get('cmsCollectionID'),
            'objectType': src.get('type'),
            'objectFormat': src.get('format')
        }

def has_mezzanines(file_path):
    for parent in file_path.parents:
        mezzanines_dir = parent / "Mezzanines"
        if mezzanines_dir.is_dir():
            return True
    return False

def extract_iso_file_format(file_path):
    command = ['isolyzer', str(file_path)]
    try:
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        xml_output = process.stdout
        root = ET.fromstring(xml_output)
        
        # Find the fileSystem element
        file_system_element = root.find(".//{http://kb.nl/ns/isolyzer/v1/}fileSystem")
        
        if file_system_element is not None:
            file_system_type = file_system_element.attrib.get('TYPE')
            logging.info(f"Extracted ISO file format: {file_system_type}")
            return file_system_type
        else:
            logging.error(f"FileSystem element not found in Isolyzer output for file: {file_path}")
            logging.debug(f"Isolyzer output: {xml_output}")
            return None
        
    except subprocess.CalledProcessError as e:
        logging.error(f"Isolyzer failed with error: {e}")
        return None
    except ET.ParseError as e:
        logging.error(f"Failed to parse Isolyzer XML output: {e}")
        logging.debug(f"Isolyzer output: {xml_output}")
        return None


def extract_track_info(media_info, path, valid_extensions):
    # the pattern to match YYYY-MM-DD
    pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
    for track in media_info.tracks:
        if track.track_type == "General":
            file_format = track.format
            if file_format is None and path.suffix.lower() == '.iso':
                file_format = extract_iso_file_format(path)

            file_data = [
                path,
                '.'.join([path.stem, path.suffix[1:]]),
                path.stem,
                path.suffix[1:],
                track.file_size,
                pattern.search(track.file_last_modification_date).group(0) if pattern.search(track.file_last_modification_date) else None,
                file_format,
                track.audio_format_list.split()[0] if track.audio_format_list else None,
                track.codecs_video,
                track.duration,
            ]

            if track.duration:
                human_duration = str(track.other_duration[3]) if track.other_duration else None
                file_data.append(human_duration)
            else:
                file_data.append(None)

            media_type = None
            has_mezzanines_folder = has_mezzanines(path)

            if path.suffix.lower() in video_extensions:
                media_type = 'film' if has_mezzanines_folder else 'video'
            elif path.suffix.lower() in audio_extensions:
                media_type = 'audio'

            file_data.append(media_type)
            file_no_ext = path.stem
            role = file_no_ext.split('_')[-1]
            division = file_no_ext.split('_')[0]
            driveID = path.parts[2]
            file_data.extend([role, division, driveID])
            primaryID = path.stem
            file_data.append(primaryID.split('_')[1] if len(primaryID.split('_')) > 1 else None)

            return file_data

    return None

def is_tool(name):
    # Check whether `name` is on PATH and marked as executable.
    from shutil import which
    return which(name) is not None

def main():
    parser = make_parser()
    args = parser.parse_args()

    top_directory = Path(args.directory)
    if not top_directory.is_dir():
        logging.error('Invalid directory path')
        return

    bags = process_bags(top_directory)
    files_to_examine = []

    # Process each bag if present
    if args.vendor and bags:
        for bag in bags:
            files = process_directory(bag, process_json=args.vendor)
            files_to_examine.extend(files)
            if files:
                logging.info(f"Processing {len(files)} files from {bag}")
    else:
        # If no bags are present, assume the directory contains loose media files
        for path in top_directory.rglob('*'):
            if path.is_file() and path.suffix.lower() in video_extensions.union(audio_extensions):
                if path.name.startswith("._"):
                    logging.info(f"Skipping hidden Mac file: {path}")
                else:
                    files_to_examine.append(path)
                    logging.info(f"Adding file to processing list: {path}")

    if not files_to_examine:
        logging.error('No media files found')
        return

    all_file_data = []
    for path in files_to_examine:
        media_info = MediaInfo.parse(str(path))
        file_data = extract_track_info(media_info, path, video_extensions.union(audio_extensions))
        if file_data:
            if args.vendor:
                json_path = path.with_suffix('.json')
                if json_path.exists():
                    json_data = read_json_sidecar(json_path)
                    file_data.extend([json_data['collectionID'], json_data['objectType'], json_data['objectFormat']])
            all_file_data.append(file_data)
            logging.info(f"Processed file data for: {path}")

    with open(args.output, 'w', newline='') as f:
        md_csv = csv.writer(f)
        header = [
            'filePath',
            'asset.referenceFilename',
            'technical.filename',
            'technical.extension',
            'technical.fileSize.measure',
            'technical.dateCreated',
            'technical.fileFormat',
            'technical.audioCodec',
            'technical.videoCodec',
            'technical.durationMilli.measure',
            'technical.durationHuman',
            'mediaType',
            'role',
            'divisionCode',
            'driveID',
            'primaryID',
            'collectionID',  # Added from JSON
            'objectType',    # Added from JSON
            'objectFormat'   # Added from JSON
        ]
        md_csv.writerow(header)
        md_csv.writerows(all_file_data)
        logging.info(f"CSV file created successfully at {args.output}")

if __name__ == "__main__":
    main()
