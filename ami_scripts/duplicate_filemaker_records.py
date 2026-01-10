#!/usr/bin/env python3

import os
import jaydebeapi
import logging
from pathlib import Path
import argparse
from collections import defaultdict
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Summary counters
summary = {
    'inserted': 0,
    'skipped': 0,
    'errors': 0,
}

# Define media format extensions
# Note: .mp4 is classified as VIDEO, but the logic allows it to be a derivative of AUDIO PMs
VIDEO_EXTENSIONS = {'.mkv', '.mov', '.mp4', '.dv', '.iso', '.m4v'}
AUDIO_EXTENSIONS = {'.wav', '.flac', '.aea', '.mp3'}
ALL_MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Script to duplicate FileMaker records for media derivatives.')
parser.add_argument('-d', '--directory', required=True, help='Path to the directory containing media files.')
parser.add_argument('--dev-server', action='store_true', help='Connect to the DEV server instead of the production server.')
args = parser.parse_args()

# Determine which server to connect to
if args.dev_server:
    server_ip = os.getenv('FM_DEV_SERVER')
    logging.info("Connecting to the test server.")
else:
    server_ip = os.getenv('FM_SERVER')
    logging.info("Connecting to the production server.")

# Load other environment variables
database_name = os.getenv('AMI_DATABASE')
username = os.getenv('AMI_DATABASE_USERNAME')
password = os.getenv('AMI_DATABASE_PASSWORD')
jdbc_path = os.path.expanduser('~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar')

# Connect to the database
def connect_to_database():
    try:
        conn = jaydebeapi.connect(
            'com.filemaker.jdbc.Driver',
            f'jdbc:filemaker://{server_ip}/{database_name}',
            [username, password],
            jdbc_path
        )
        logging.info("Connected to the database.")
        return conn
    except Exception as e:
        logging.error(f"Failed to connect to the database: {e}")
        return None

# Parse filename components
def parse_filename(filename):
    """Parse filename to extract base identifier, version, face, region/stream, take, role, and extension."""
    stem = Path(filename).stem
    ext = Path(filename).suffix.lower()
    
    # Pattern to match: identifier_version[face][region/stream][take]_role
    # This regex is robust and covers both Video (DVD/MKV) and Audio (FLAC/MP4-SC) workflows
    # Examples: 
    # - myd_123456_v01_pm
    # - myd_123456_v01f01_pm
    # - myd_123456_v01f01r02_sc
    # - myd_330487_v01f01_sc (Audio Service Copy in MP4 container)
    
    pattern = r'^(.+_v\d+)(f\d+)?([rs]\d+)?(t\d+)?_([a-z]+)$'
    match = re.match(pattern, stem)
    
    if match:
        base_id = match.group(1)     # e.g., "scb_999999_v01"
        face = match.group(2)        # e.g., "f01" or None
        region_or_stream = match.group(3)  # e.g., "r02", "s01" or None
        take = match.group(4)        # e.g., "t01" or None
        role = match.group(5)        # e.g., "pm", "sc", "em", "mz"
        
        # Determine if this is a region or stream
        region = None
        stream = None
        if region_or_stream:
            if region_or_stream.startswith('r'):
                region = region_or_stream
            elif region_or_stream.startswith('s'):
                stream = region_or_stream
        
        return {
            'base_id': base_id,
            'face': face,
            'region': region,
            'stream': stream,
            'take': take,
            'role': role,
            'extension': ext,
            'full_stem': stem,
            'filename': filename,
            'is_multitrack': stream is not None
        }
    
    # --- Fallback Logic for Legacy/Odd Filenames ---

    # Fallback for DVD-style ISO filenames
    if '_pm' in stem and ext == '.iso':
        base_id = stem.replace('_pm', '')
        return {
            'base_id': base_id,
            'face': None,
            'region': None,
            'stream': None,
            'take': None,
            'role': 'pm',
            'extension': ext,
            'full_stem': stem,
            'filename': filename,
            'is_multitrack': False
        }
    
    # Fallback for DVD MP4 with explicit face/region in non-standard format
    elif ext == '.mp4' and ('f' in stem and 'r' in stem):
        mp4_key = stem.split('f')[0]
        return {
            'base_id': mp4_key,
            'face': 'f' + stem.split('f')[1].split('r')[0] if 'f' in stem else None,
            'region': 'r' + stem.split('r')[1].split('_')[0] if 'r' in stem else None,
            'stream': None,
            'take': None,
            'role': 'sc',
            'extension': ext,
            'full_stem': stem,
            'filename': filename,
            'is_multitrack': False
        }
    
    # Fallback for generic Service Copies (Video or Audio-as-Video) that failed regex
    elif ext == '.mp4' and stem.endswith('_sc'):
        # Careful: If the file is myd_v01f01_sc.mp4 and regex failed, 
        # simplistic stripping might leave 'f01' in the base_id, preventing matching.
        # This fallback assumes the filename is simple: myd_123_v01_sc.mp4
        base_id = stem[:-3].rstrip('_')
        return {
            'base_id': base_id,
            'face': None,
            'region': None,
            'stream': None,
            'take': None,
            'role': 'sc',
            'extension': ext,
            'full_stem': stem,
            'filename': filename,
            'is_multitrack': False
        }
    
    return None

# Crawl directory and organize files by format type
def crawl_directory(directory):
    """Crawl directory recursively and organize files by media type and base identifier."""
    file_groups = defaultdict(lambda: {'pm_files': [], 'derivative_files': []})
    
    # Walk through all subdirectories (includes PreservationMasters, EditMasters, ServiceCopies)
    for root, dirs, files in os.walk(directory):
        for file in files:
            filepath = Path(root) / file
            # Check against set of all allowed extensions
            if filepath.suffix.lower() in ALL_MEDIA_EXTENSIONS:
                parsed = parse_filename(file)
                if parsed:
                    base_id = parsed['base_id']
                    
                    # Group logic
                    if parsed['role'] == 'pm':
                        file_groups[base_id]['pm_files'].append({
                            'path': filepath,
                            'parsed': parsed,
                            'media_type': 'video' if parsed['extension'] in VIDEO_EXTENSIONS else 'audio'
                        })
                    else:
                        file_groups[base_id]['derivative_files'].append({
                            'path': filepath,
                            'parsed': parsed,
                            # Note: SC MP4s from Audio will be tagged 'video' here, which is fine
                            'media_type': 'video' if parsed['extension'] in VIDEO_EXTENSIONS else 'audio'
                        })
                    
                    logging.debug(f"Parsed {file}: {parsed}")
    
    result = dict(file_groups)
    logging.info(f"Found {len(result)} file groups")
    for base_id, group in result.items():
        logging.info(f"  {base_id}: {len(group['pm_files'])} PM files, {len(group['derivative_files'])} derivative files")
    
    return result

def fetch_original_record(conn, reference_filename):
    curs = conn.cursor()
    try:
        query = 'SELECT * FROM tbl_metadata WHERE "asset.referenceFilename" = ?'
        logging.info(f"Fetching record with asset.referenceFilename = {reference_filename}")
        curs.execute(query, [reference_filename])
        record = curs.fetchone()
        if record:
            columns = [desc[0] for desc in curs.description]
            record_dict = {}
            
            for col, value in zip(columns, record):
                if value is None or value == '':
                    record_dict[col] = None
                elif isinstance(value, float):
                    if col == 'source.audioRecording.numberOfAudioTracks':
                        if value.is_integer():
                            record_dict[col] = int(value)
                        else:
                            record_dict[col] = value
                    elif value == 0.0:
                        record_dict[col] = None
                    elif value.is_integer():
                        record_dict[col] = int(value)
                    else:
                        record_dict[col] = value
                else:
                    record_dict[col] = value

            fields_as_strings = ['asset.schemaVersion', 'bibliographic.barcode']
            for field in fields_as_strings:
                if field in record_dict and record_dict[field] is not None:
                    record_dict[field] = str(record_dict[field])

            return record_dict
        else:
            logging.error(f"No record found for {reference_filename}.")
            return None
    except Exception as e:
        logging.error(f"Error fetching record: {e}")
        return None
    finally:
        curs.close()

def check_record_exists(conn, filename):
    curs = conn.cursor()
    try:
        query = 'SELECT COUNT(*) FROM tbl_metadata WHERE "asset.referenceFilename" = ?'
        curs.execute(query, [filename])
        count = curs.fetchone()[0]
        return count > 0
    except Exception as e:
        logging.error(f"Error checking if record exists for {filename}: {e}")
        return False
    finally:
        curs.close()

def insert_new_record(conn, original_record, target_file_info, face_number=None, region_number=None, stream_number=None, take_number=None):
    global summary
    curs = conn.cursor()
    try:
        if face_number is None: face_number = ''
        if region_number is None: region_number = ''
        if stream_number is None: stream_number = ''
        if take_number is None: take_number = ''

        allowed_prefixes = ("bibliographic.", "digitizationProcess.", "digitizer.", "source.")

        filtered_record = {
            key: value for key, value in original_record.items()
            if key.startswith(allowed_prefixes)
        }

        additional_fields = [
            'WorkOrderID',
            'projectType',
            'Archival box barcode',
            'Archival box number',
            'asset.schemaVersion',
            'technical.signalNotes'
        ]
        for field in additional_fields:
            if field in original_record:
                filtered_record[field] = original_record[field]

        parsed = target_file_info['parsed']
        
        # Determine clean extension (remove dot)
        clean_ext = parsed['extension'][1:] if parsed['extension'].startswith('.') else parsed['extension']

        filtered_record.update({
            'asset.fileRole': parsed['role'],
            'asset.fileExt': clean_ext,
            'source.subObject.faceNumber': face_number,
            'source.subObject.regionNumber': region_number,
            'digitizationProcess.takeNumber.number': take_number,
        })
        
        if stream_number:
            filtered_record['source.subObject.streamNumber'] = stream_number

        # Check types for NULL handling
        curs.execute("SELECT * FROM tbl_metadata WHERE 1=0")
        
        insert_values = {}
        for key, value in filtered_record.items():
            if value is None or value == '':
                insert_values[key] = None
            elif isinstance(value, float):
                if key == 'source.audioRecording.numberOfAudioTracks':
                    if value.is_integer():
                        insert_values[key] = int(value)
                    else:
                        insert_values[key] = value
                elif value == 0.0:
                    insert_values[key] = None
                elif value.is_integer():
                    insert_values[key] = int(value)
                else:
                    insert_values[key] = value
            else:
                insert_values[key] = value

        columns = ', '.join(f'"{col}"' for col in insert_values.keys())
        placeholders = ', '.join(['?'] * len(insert_values))
        sql = f"INSERT INTO tbl_metadata ({columns}) VALUES ({placeholders})"
        values = list(insert_values.values())

        logging.info(f"Inserting new record for file: {target_file_info['parsed']['filename']}")
        summary['inserted'] += 1
        
        curs.execute(sql, values)
        conn.commit()
        logging.info("New record inserted successfully.")
    except Exception as e:
        logging.error(f"Failed to insert new record: {e}")
        summary['errors'] += 1
        conn.rollback()
    finally:
        curs.close()

def extract_face_number(parsed_data):
    if parsed_data['face']:
        try:
            return int(parsed_data['face'][1:])
        except ValueError:
            return None
    return None

def extract_region_number(parsed_data):
    if parsed_data['region']:
        try:
            return int(parsed_data['region'][1:])
        except ValueError:
            return None
    return None

def extract_stream_number(parsed_data):
    if parsed_data['stream']:
        try:
            return int(parsed_data['stream'][1:])
        except ValueError:
            return None
    return None

def extract_take_number(parsed_data):
    if parsed_data['take']:
        try:
            return int(parsed_data['take'][1:])
        except ValueError:
            return None
    return None

def find_primary_pm_file(pm_files):
    """Find the primary PM file to use as the database reference."""
    if not pm_files:
        return None
    
    has_multitrack = any(f['parsed']['is_multitrack'] for f in pm_files)
    
    if has_multitrack:
        for pm_file in pm_files:
            parsed = pm_file['parsed']
            if parsed['face'] == 'f01' and parsed['stream'] == 's01':
                return pm_file
        multitrack_files = [f for f in pm_files if f['parsed']['is_multitrack']]
        if multitrack_files:
            return multitrack_files[0]
    
    audio_files = [f for f in pm_files if f['media_type'] == 'audio']
    if audio_files:
        f01_files = [f for f in audio_files if f['parsed']['face'] == 'f01']
        if f01_files:
            f01t01_files = [f for f in f01_files if f['parsed']['take'] == 't01']
            if f01t01_files:
                return f01t01_files[0]
            return f01_files[0]
        return audio_files[0]
    
    # If no audio files, return the first available file (video behavior)
    return pm_files[0]

def process_file_group(conn, base_id, file_group):
    global summary
    pm_files = sorted(file_group['pm_files'], key=lambda x: x['parsed']['filename'])
    derivative_files = sorted(file_group['derivative_files'], key=lambda x: x['parsed']['filename'])
    
    if not pm_files:
        logging.warning(f"No PM files found for {base_id}. Skipping.")
        return
    
    has_multitrack = any(f['parsed']['is_multitrack'] for f in pm_files + derivative_files)
    
    if has_multitrack:
        process_multitrack_file_group(conn, base_id, pm_files, derivative_files)
    else:
        process_standard_file_group(conn, base_id, pm_files, derivative_files)

def process_standard_file_group(conn, base_id, pm_files, derivative_files):
    primary_pm = find_primary_pm_file(pm_files)
    if not primary_pm:
        logging.error(f"Could not determine primary PM file for {base_id}. Skipping.")
        return
    
    reference_filename = primary_pm['parsed']['filename']
    logging.info(f"Processing standard file group: {base_id}")
    logging.info(f"Primary PM file: {reference_filename}")
    
    original_record = fetch_original_record(conn, reference_filename)
    if not original_record:
        logging.error(f"Original record not found for {reference_filename}. Skipping.")
        return
    
    # Lookup dictionaries
    pm_by_face_region_take = {}
    pm_by_face_region = {}
    pm_by_face        = {}
    for pm_file in pm_files:
        f = pm_file['parsed']['face']
        r = pm_file['parsed']['region']
        t = pm_file['parsed']['take']

        pm_by_face_region_take[(f, r, t)] = pm_file
        
        if (f, r) not in pm_by_face_region:
            pm_by_face_region[(f, r)] = pm_file
            
        if f not in pm_by_face:
            pm_by_face[f] = pm_file
    
    # Process duplicate PMs
    for pm_file in pm_files:
        if pm_file is primary_pm:
            continue
        target_filename = pm_file['parsed']['filename']
        if check_record_exists(conn, target_filename):
            logging.info(f"Record already exists for {target_filename}. Skipping creation.")
            summary['skipped'] += 1
            continue
        face_number = extract_face_number(pm_file['parsed'])
        region_number = extract_region_number(pm_file['parsed'])
        take_number = extract_take_number(pm_file['parsed'])
        insert_new_record(conn, original_record, pm_file, face_number, region_number, None, take_number)
    
    # Process derivatives (EMs and SCs)
    # This logic handles Audio SCs (.mp4) correctly matching Audio PMs (.flac) via Face ID
    for derivative_file in derivative_files:
        parsed = derivative_file['parsed']
        target_filename = parsed['filename']
        if check_record_exists(conn, target_filename):
            logging.info(f"Record already exists for {target_filename}. Skipping creation.")
            summary['skipped'] += 1
            continue
        
        face   = parsed['face']
        region = parsed['region']
        take   = parsed['take']
        
        # 1) Try exact face+region+take match
        source_pm = pm_by_face_region_take.get((face, region, take))
        
        # 2) Fallback to face+region (ignoring take)
        if source_pm is None:
            source_pm = pm_by_face_region.get((face, region))

        # 3) Fallback to face-only (ignoring region and take)
        if source_pm is None and face in pm_by_face:
            source_pm = pm_by_face[face]
            
        # 4) Ultimate fallback to primary PM
        if source_pm is None:
            source_pm = primary_pm
        
        logging.info(f"Using {source_pm['parsed']['filename']} as source for {target_filename}")
        
        source_record = fetch_original_record(conn, source_pm['parsed']['filename'])
        if not source_record:
            logging.warning(f"Could not fetch record for {source_pm['parsed']['filename']}, falling back to primary")
            source_record = original_record
        
        face_number   = extract_face_number(parsed)
        region_number = extract_region_number(parsed)
        take_number   = extract_take_number(parsed)
        insert_new_record(conn, source_record, derivative_file, face_number, region_number, None, take_number)

def process_multitrack_file_group(conn, base_id, pm_files, derivative_files):
    logging.info(f"Processing multitrack file group: {base_id}")
    
    pm_by_face_stream = {}
    pm_by_face = {}
    
    for pm_file in pm_files:
        f = pm_file['parsed']['face']
        s = pm_file['parsed']['stream']
        pm_by_face_stream[(f, s)] = pm_file
        if f not in pm_by_face:
            pm_by_face[f] = pm_file
    
    primary_pm = None
    for pm_file in pm_files:
        parsed = pm_file['parsed']
        if parsed['face'] == 'f01' and parsed['stream'] == 's01':
            primary_pm = pm_file
            break
    
    if not primary_pm:
        primary_pm = pm_files[0]
    
    reference_filename = primary_pm['parsed']['filename']
    logging.info(f"Primary PM file: {reference_filename}")
    
    original_record = fetch_original_record(conn, reference_filename)
    if not original_record:
        logging.error(f"Original record not found for {reference_filename}. Skipping.")
        return
    
    missing_pm_streams = []
    for pm_file in pm_files:
        if pm_file is primary_pm:
            continue
        target_filename = pm_file['parsed']['filename']
        if not check_record_exists(conn, target_filename):
            missing_pm_streams.append(pm_file)
        else:
            logging.info(f"PM record already exists for {target_filename}")
            summary['skipped'] += 1
    
    for pm_file in missing_pm_streams:
        face_number = extract_face_number(pm_file['parsed'])
        stream_number = extract_stream_number(pm_file['parsed'])
        insert_new_record(conn, original_record, pm_file, face_number, None, stream_number, None)
    
    for derivative_file in derivative_files:
        parsed = derivative_file['parsed']
        target_filename = parsed['filename']
        
        if check_record_exists(conn, target_filename):
            logging.info(f"Record already exists for {target_filename}. Skipping creation.")
            summary['skipped'] += 1
            continue
        
        face = parsed['face']
        stream = parsed['stream']
        
        source_pm = pm_by_face_stream.get((face, stream))
        if source_pm is None:
            if face in pm_by_face:
                source_pm = pm_by_face[face]
            else:
                source_pm = primary_pm
        
        logging.info(f"Using {source_pm['parsed']['filename']} as source for {target_filename}")
        
        source_record = fetch_original_record(conn, source_pm['parsed']['filename'])
        if not source_record:
            logging.warning(f"Could not fetch record for {source_pm['parsed']['filename']}, falling back to primary")
            source_record = original_record
        
        face_number = extract_face_number(parsed)
        stream_number = extract_stream_number(parsed)
        insert_new_record(conn, source_record, derivative_file, face_number, None, stream_number, None)

def duplicate_records(conn, file_groups):
    for base_id, file_group in file_groups.items():
        try:
            process_file_group(conn, base_id, file_group)
        except Exception as e:
            logging.error(f"Error processing file group {base_id}: {e}")
            continue

def main():
    directory = args.directory
    conn = connect_to_database()
    if not conn:
        return
    try:
        file_groups = crawl_directory(directory)
        duplicate_records(conn, file_groups)
    finally:
        conn.close()

    logger.info("")
    logger.info("✅ ===== Summary =====")
    logger.info(f"✅ Records inserted: {summary['inserted']}")
    logger.info(f"✅ Records skipped : {summary['skipped']}")
    logger.info(f"❌ Errors          : {summary['errors']}")
    logger.info("✅ ===================")

if __name__ == '__main__':
    main()