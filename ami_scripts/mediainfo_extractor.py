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
from datetime import datetime, timedelta
from pymediainfo import MediaInfo
import jaydebeapi
import os


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

video_extensions = {'.mkv', '.mov', '.mp4', '.dv', '.iso'}
audio_extensions = {'.wav', '.flac', '.aea'}

def make_parser():
    parser = argparse.ArgumentParser(description="Pull MediaInfo from a bunch of video or audio files")
    parser.add_argument("-d", "--directory",
                        help="path to folder full of media files",
                        required=False)
    parser.add_argument("-f", "--file",
                        help="path to folder full of media files",
                        required=False)
    parser.add_argument("-o", "--output",
                        help="path to save csv")
    parser.add_argument("-v", "--vendor", action='store_true', 
                        help="process as BagIt with sidecar JSON metadata")

    return parser

def filter_for_jdbc(record):
    jdbc_fields = [
        "asset.referenceFilename",
        "technical.filename",
        "technical.extension",
        "technical.fileSize.measure",
        "technical.dateCreated",
        "technical.dateCreatedText",
        "technical.fileFormat",
        "technical.audioCodec",
        "technical.videoCodec",
        "technical.durationMilli.measure",
        "technical.durationHuman",
        "inhouse_bag_batch_id"
    ]
    return {k: record[k] for k in jdbc_fields if k in record}

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
    with open(json_path, 'r', encoding='utf-8-sig') as f:
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

def extract_with_ffprobe(path: Path):
    """Use ffprobe to pull basic info and format duration as HH:MM:SS.mmm."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        str(path)
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(proc.stdout).get('format', {})
    streams = json.loads(proc.stdout).get('streams', [])

    # Raw values
    size       = int(info.get('size',    0))
    duration_s = float(info.get('duration', 0.0))
    fmt_name   = info.get('format_name')
    audio_codec = next((s['codec_name'] for s in streams if s.get('codec_type')=='audio'), None)
    video_codec = next((s['codec_name'] for s in streams if s.get('codec_type')=='video'), None)

    # Build HH:MM:SS.mmm
    hrs    = int(duration_s // 3600)
    rem    = duration_s - hrs * 3600
    mins   = int(rem // 60)
    rem2   = rem - mins * 60
    secs   = int(rem2)
    ms     = int(round((rem2 - secs) * 1000))
    # handle rounding overflow
    if ms == 1000:
        secs += 1
        ms = 0
        if secs == 60:
            mins += 1
            secs = 0
            if mins == 60:
                hrs += 1
                mins = 0
    human_dur = f"{hrs:02d}:{mins:02d}:{secs:02d}.{ms:03d}"

    # file’s mtime as YYYY-MM-DD
    date_str = datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d')

    return {
        'file_size': size,
        'duration_s': duration_s,
        'human_duration': human_dur,
        'file_format': fmt_name,
        'audio_codec': audio_codec,
        'video_codec': video_codec,
        'date_created': date_str,
    }

def extract_track_info(media_info, path, valid_extensions):

    suffix = path.suffix.lower()

    # --- Special case for .aea (MiniDisc) files ---
    if suffix == '.aea':
        ff = extract_with_ffprobe(path)

        file_no_ext = path.stem
        role     = file_no_ext.split('_')[-1]
        division = file_no_ext.split('_')[0]
        driveID  = path.parts[2] if len(path.parts) > 2 else None
        primaryID = file_no_ext.split('_')[1] if len(file_no_ext.split('_')) > 1 else None
        bag_id = next((part for part in path.parts if part.startswith("MDR")), None)

        return [
            path,                                        # filePath
            f"{path.stem}{suffix}",                      # asset.referenceFilename
            path.stem,                                   # technical.filename
            suffix[1:],                                  # technical.extension
            ff['file_size'],                             # technical.fileSize.measure
            ff['date_created'],                          # technical.dateCreated
            ff['file_format'],                           # technical.fileFormat
            ff['audio_codec'],                           # technical.audioCodec
            ff['video_codec'],                           # technical.videoCodec
            int(ff['duration_s'] * 1000),                # technical.durationMilli.measure
            ff['human_duration'],                        # technical.durationHuman
            'audio',                                     # mediaType
            role,                                        # asset.fileRole
            division,                                    # bibliographic.vernacularDivisionCode
            driveID,                                     # driveID
            primaryID,                                   # bibliographic.primaryID
            bag_id                                       # MDR WorkOrder
        ]
    
    # --- Fallback for everything else (Video & WAV/FLAC) ---
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

            bag_id = next((part for part in path.parts if part.startswith("MDR")), None)
            print(bag_id)
            file_data.append(bag_id)  

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
    
    all_file_data.sort(key=lambda row: str(row[0]))

    # duplicate dateCreated into a second column
    for row in all_file_data:
        row.insert(6, row[5])

    if args.output:
        with open(args.output, 'w', newline='') as f:
            md_csv = csv.writer(f)
            header = [
                'filePath',
                'asset.referenceFilename',
                'technical.filename',
                'technical.extension',
                'technical.fileSize.measure',
                'technical.dateCreated',
                'technical.dateCreatedText',
                'technical.fileFormat',
                'technical.audioCodec',
                'technical.videoCodec',
                'technical.durationMilli.measure',
                'technical.durationHuman',
                'mediaType',
                'asset.fileRole',
                'bibliographic.vernacularDivisionCode',
                'driveID',
                'bibliographic.primaryID',
                'bibliographic.cmsCollectionID',
                'source.object.type',
                'source.object.format'
            ]
            md_csv.writerow(header)
            md_csv.writerows(all_file_data)
            logging.info(f"CSV file created successfully at {args.output}")
    else:
        server_ip = os.getenv('FM_SERVER')
        database_name = os.getenv('AMI_DATABASE')
        username = os.getenv('AMI_DATABASE_USERNAME')
        password = os.getenv('AMI_DATABASE_PASSWORD')
        jdbc_path = os.path.expanduser('~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar')

        def insert_records(conn, insert_data):
            curs = conn.cursor()
            try:
                for record in insert_data:
                    placeholders = ', '.join(['?'] * len(record))
                    columns = ', '.join(f'"{col}"' for col in record.keys())
                    sql = f"INSERT INTO tbl_techinfo ({columns}) VALUES ({placeholders})"
                    print(f"Executing SQL: {sql} with values {list(record.values())}")
                    curs.execute(sql, list(record.values()))
                conn.commit()
                logging.info("Records inserted successfully into tbl_techinfo.")
            except Exception as e:
                logging.error(f"Failed to insert records: {e}")
                conn.rollback()

        def check_corresponding_records(conn, filenames):
            curs = conn.cursor()
            found, not_found = 0, 0
            logging.info(f"Checking for corresponding records for {len(filenames)} media files in the PRODUCTION table.")
            for filename in filenames:
                curs.execute('SELECT COUNT(*) FROM tbl_metadata WHERE "asset.referenceFilename" = ?', [filename])
                if curs.fetchone()[0] > 0:
                    found += 1
                    logging.info(f"✓ Found: {filename}")
                else:
                    not_found += 1
                    logging.warning(f"✗ Not found: {filename}")
            logging.info(f"{found} corresponding records found.")
            logging.info(f"{not_found} corresponding records not found.")

        # Convert flat rows to dicts for JDBC
        field_names = [
            'asset.referenceFilename',
            'technical.filename',
            'technical.extension',
            'technical.fileSize.measure',
            'technical.dateCreated',
            'technical.dateCreatedText',
            'technical.fileFormat',
            'technical.audioCodec',
            'technical.videoCodec',
            'technical.durationMilli.measure',
            'technical.durationHuman',
            'mediaType',
            'asset.fileRole',
            'bibliographic.vernacularDivisionCode',
            'driveID',
            'bibliographic.primaryID',
            'bibliographic.cmsCollectionID',
            'source.object.type',
            'source.object.format',
            'inhouse_bag_batch_id'
        ]
        all_records = []
        filenames = []

        for row in all_file_data:
            full_record = dict(zip(field_names, row[1:]))  # skip filePath
            all_records.append(full_record)
            filenames.append(full_record['asset.referenceFilename'])

        # ✅ Filter only the fields we want to insert into the DB
        insert_data = [filter_for_jdbc(r) for r in all_records]

        try:
            conn = jaydebeapi.connect(
                'com.filemaker.jdbc.Driver',
                f'jdbc:filemaker://{server_ip}/{database_name}',
                [username, password],
                jdbc_path
            )
            logging.info("Connection to AMIDB successful!")
            check_corresponding_records(conn, filenames)
            insert_records(conn, insert_data)
        except Exception as e:
            logging.error(f"Database connection or execution error: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

if __name__ == "__main__":
    main()