#!/usr/bin/env python3

import os
import jaydebeapi
import logging
from pathlib import Path
import argparse
from collections import defaultdict
import re

# Configure logging
logging.basicConfig(level=logging.INFO)

# Define media format extensions
VIDEO_EXTENSIONS = {'.mkv', '.mov', '.mp4', '.dv', '.iso'}
AUDIO_EXTENSIONS = {'.wav', '.flac', '.aea'}
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
    """Parse filename to extract base identifier, version, face, region, role, and extension."""
    stem = Path(filename).stem
    ext = Path(filename).suffix.lower()
    
    # Pattern to match: identifier_version[face][region]_role
    # Examples: myd_123456_v01_pm, myd_123456_v01f01_pm, myd_123456_v01f01r02_sc
    pattern = r'^(.+_v\d+)(f\d+)?(r\d+)?_([a-z]+)$'
    match = re.match(pattern, stem)
    
    if match:
        base_id = match.group(1)  # e.g., "myd_123456_v01"
        face = match.group(2)     # e.g., "f01" or None
        region = match.group(3)   # e.g., "r02" or None
        role = match.group(4)     # e.g., "pm", "sc", "em", "mz"
        
        return {
            'base_id': base_id,
            'face': face,
            'region': region,
            'role': role,
            'extension': ext,
            'full_stem': stem,
            'filename': filename
        }
    
    # Fallback for DVD-style filenames (backwards compatibility)
    if '_pm' in stem and ext == '.iso':
        base_id = stem.replace('_pm', '')
        return {
            'base_id': base_id,
            'face': None,
            'region': None,
            'role': 'pm',
            'extension': ext,
            'full_stem': stem,
            'filename': filename
        }
    elif ext == '.mp4' and ('f' in stem and 'r' in stem):
        # DVD MP4 with face/region
        mp4_key = stem.split('f')[0]
        return {
            'base_id': mp4_key,
            'face': 'f' + stem.split('f')[1].split('r')[0] if 'f' in stem else None,
            'region': 'r' + stem.split('r')[1].split('_')[0] if 'r' in stem else None,
            'role': 'sc',
            'extension': ext,
            'full_stem': stem,
            'filename': filename
        }
    elif ext == '.mp4' and stem.endswith('_sc'):
        # DVD MP4 service copy
        base_id = stem[:-3].rstrip('_')
        return {
            'base_id': base_id,
            'face': None,
            'region': None,
            'role': 'sc',
            'extension': ext,
            'full_stem': stem,
            'filename': filename
        }
    
    return None

# Crawl directory and organize files by format type
def crawl_directory(directory):
    """Crawl directory recursively and organize files by media type and base identifier."""
    file_groups = defaultdict(lambda: {'pm_files': [], 'derivative_files': []})
    
    # Walk through all subdirectories
    for root, dirs, files in os.walk(directory):
        for file in files:
            filepath = Path(root) / file
            if filepath.suffix.lower() in ALL_MEDIA_EXTENSIONS:
                parsed = parse_filename(file)
                if parsed:
                    base_id = parsed['base_id']
                    
                    # Determine if this is a preservation master or derivative
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
                            'media_type': 'video' if parsed['extension'] in VIDEO_EXTENSIONS else 'audio'
                        })
                    
                    logging.debug(f"Parsed {file}: {parsed}")
    
    # Convert defaultdict to regular dict for logging
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
            # Get the column types from cursor description
            column_types = {desc[0]: desc[1] for desc in curs.description}
            record_dict = {}
            
            # Process each field with awareness of its original type
            for col, value in zip(columns, record):
                if value is None or value == '':
                    record_dict[col] = None
                elif isinstance(value, float):
                    # Special case: preserve 0 values for numberOfAudioTracks field
                    if col == 'source.audioRecording.numberOfAudioTracks':
                        if value.is_integer():
                            record_dict[col] = int(value)
                        else:
                            record_dict[col] = value
                    elif value == 0.0:
                        # Check if this was actually a blank in the original
                        record_dict[col] = None
                    elif value.is_integer():
                        record_dict[col] = int(value)
                    else:
                        record_dict[col] = value
                else:
                    record_dict[col] = value

            # Fields that should always be treated as strings
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
    """Check if a record already exists for the given filename."""
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

def insert_new_record(conn, original_record, target_file_info, face_number=None, region_number=None):
    curs = conn.cursor()
    try:
        # Set default values if face_number or region_number are None
        if face_number is None:
            face_number = ''
        if region_number is None:
            region_number = ''

        # Define allowed prefixes
        allowed_prefixes = ("bibliographic.", "digitizationProcess.", "digitizer.", "source.")

        # Dynamically filter fields based on allowed prefixes
        filtered_record = {
            key: value for key, value in original_record.items()
            if key.startswith(allowed_prefixes)
        }

        # Explicitly add additional fields
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

        # Add or override fields specific to the new record
        parsed = target_file_info['parsed']
        filtered_record.update({
            'asset.fileRole': parsed['role'],
            'asset.fileExt': parsed['extension'][1:],  # Remove the dot
            'source.subObject.faceNumber': face_number,
            'source.subObject.regionNumber': region_number,
        })

        # Get table column information to identify numeric fields
        curs.execute("SELECT * FROM tbl_metadata WHERE 1=0")  # Empty result set just to get column info
        column_info = {desc[0]: desc[1] for desc in curs.description}

        # Prepare values for insertion
        insert_values = {}
        for key, value in filtered_record.items():
            if value is None or value == '':
                insert_values[key] = None
            elif isinstance(value, float):
                # Special case: preserve 0 values for numberOfAudioTracks field
                if key == 'source.audioRecording.numberOfAudioTracks':
                    if value.is_integer():
                        insert_values[key] = int(value)
                    else:
                        insert_values[key] = value
                elif value == 0.0:
                    # Preserve as NULL for numeric fields
                    insert_values[key] = None
                elif value.is_integer():
                    insert_values[key] = int(value)
                else:
                    insert_values[key] = value
            else:
                insert_values[key] = value

        # Prepare the insert statement
        columns = ', '.join(f'"{col}"' for col in insert_values.keys())
        placeholders = ', '.join(['?'] * len(insert_values))
        sql = f"INSERT INTO tbl_metadata ({columns}) VALUES ({placeholders})"
        values = list(insert_values.values())

        logging.info(f"Inserting new record for file: {target_file_info['parsed']['filename']}")
        logging.debug(f"SQL Statement: {sql}")
        logging.debug(f"Values: {values}")

        # Execute with explicit NULL values
        curs.execute(sql, values)
        conn.commit()
        logging.info("New record inserted successfully.")
    except Exception as e:
        logging.error(f"Failed to insert new record: {e}")
        conn.rollback()
    finally:
        curs.close()

# Extract face number from parsed filename data
def extract_face_number(parsed_data):
    if parsed_data['face']:
        try:
            return int(parsed_data['face'][1:])  # Remove 'f' prefix
        except ValueError:
            logging.warning(f"Could not extract face number from: {parsed_data['face']}")
            return None
    return None

# Extract region number from parsed filename data
def extract_region_number(parsed_data):
    if parsed_data['region']:
        try:
            return int(parsed_data['region'][1:])  # Remove 'r' prefix
        except ValueError:
            logging.warning(f"Could not extract region number from: {parsed_data['region']}")
            return None
    return None

def find_primary_pm_file(pm_files):
    """Find the primary PM file to use as the database reference."""
    if not pm_files:
        return None
    
    # For audio files, prioritize f01 if it exists, otherwise take the first one
    audio_files = [f for f in pm_files if f['media_type'] == 'audio']
    if audio_files:
        # Look for f01 files first
        f01_files = [f for f in audio_files if f['parsed']['face'] == 'f01']
        if f01_files:
            return f01_files[0]
        # Otherwise, take the first audio file
        return audio_files[0]
    
    # For video files, just take the first one
    return pm_files[0]

def process_file_group(conn, base_id, file_group):
    """Process a group of files with the same base identifier."""
    pm_files = file_group['pm_files']
    derivative_files = file_group['derivative_files']
    
    if not pm_files:
        logging.warning(f"No PM files found for {base_id}. Skipping.")
        return
    
    # Find the primary PM file to use as database reference
    primary_pm = find_primary_pm_file(pm_files)
    if not primary_pm:
        logging.error(f"Could not determine primary PM file for {base_id}. Skipping.")
        return
    
    # Construct the reference filename for database lookup
    reference_filename = primary_pm['parsed']['filename']
    logging.info(f"Processing file group: {base_id}")
    logging.info(f"Primary PM file: {reference_filename}")
    
    # Fetch the original record
    original_record = fetch_original_record(conn, reference_filename)
    if not original_record:
        logging.error(f"Original record not found for {reference_filename}. Skipping.")
        return
    
    # Create a dictionary mapping face numbers to PM files for easier lookup
    pm_by_face = {}
    for pm_file in pm_files:
        face = pm_file['parsed']['face'] or 'f01'  # Default to f01 if no face specified
        pm_by_face[face] = pm_file
    
    # Create records for all non-primary PM files (only if they don't already exist)
    for pm_file in pm_files:
        if pm_file != primary_pm:  # Skip the primary PM file
            target_filename = pm_file['parsed']['filename']
            if check_record_exists(conn, target_filename):
                logging.info(f"Record already exists for {target_filename}. Skipping creation.")
            else:
                face_number = extract_face_number(pm_file['parsed'])
                region_number = extract_region_number(pm_file['parsed'])
                insert_new_record(conn, original_record, pm_file, face_number, region_number)
    
    # Process derivative files with face-specific logic
    for derivative_file in derivative_files:
        target_filename = derivative_file['parsed']['filename']
        if check_record_exists(conn, target_filename):
            logging.info(f"Record already exists for {target_filename}. Skipping creation.")
        else:
            derivative_face = derivative_file['parsed']['face'] or 'f01'  # Default to f01 if no face specified
            
            # Find the corresponding PM file for this face
            if derivative_face in pm_by_face:
                # Use the PM file with the same face as the source record
                source_pm = pm_by_face[derivative_face]
                source_filename = source_pm['parsed']['filename']
                
                # Check if we need to fetch a different source record
                if source_pm != primary_pm:
                    # Check if the source PM record exists in the database
                    if check_record_exists(conn, source_filename):
                        source_record = fetch_original_record(conn, source_filename)
                        if source_record:
                            logging.info(f"Using {source_filename} as source for {target_filename}")
                        else:
                            logging.warning(f"Could not fetch record for {source_filename}, using primary PM record")
                            source_record = original_record
                    else:
                        logging.warning(f"Source PM record {source_filename} not found in database, using primary PM record")
                        source_record = original_record
                else:
                    source_record = original_record
                    logging.info(f"Using primary PM {reference_filename} as source for {target_filename}")
            else:
                # No matching PM face found, use primary PM
                source_record = original_record
                logging.info(f"No matching PM face found for {derivative_face}, using primary PM as source for {target_filename}")
            
            face_number = extract_face_number(derivative_file['parsed'])
            region_number = extract_region_number(derivative_file['parsed'])
            insert_new_record(conn, source_record, derivative_file, face_number, region_number)

def duplicate_records(conn, file_groups):
    """Process all file groups and duplicate records as needed."""
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

if __name__ == '__main__':
    main()