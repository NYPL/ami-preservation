#!/usr/bin/env python3
import os
import json
import jaydebeapi
import logging
from pathlib import Path
from collections import defaultdict
import argparse
import re
import pandas as pd


# Define media format extensions
VIDEO_EXTENSIONS = {'.mkv', '.mov', '.mp4', '.dv', '.iso'}
AUDIO_EXTENSIONS = {'.wav', '.flac', '.aea'}
ALL_MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

ROLE_DIRS = {
    'pm': 'PreservationMasters',
    'em': 'EditMasters',
    'sc': 'ServiceCopies',
    'mz': 'Mezzanines',
}

# Fields (top-level JSON keys) to drop entirely:
DROP_TOP_LEVEL = {
    "Archival box number",
    "Archival box barcode",
    "__zkill_workorder",
    "id",
    "__creationTimestamp",
    "_md_dp",
    "_md_s",
    "_md_t",
    "WorkOrderID",
    "__modificationTimestamp",
    "__modificationUser",
    "cmsCollectionTitle",
    "bibliographic_primaryID",
    "uk_1",
    "projectType",
    "zkill_digitizationProcess",
    "ref_ami_files_record_id",
    "cmsCollectionRepository",
    "__migrationExceptions",
    "__captureIssueCategory",
    "__captureIssueNote",
    "MARK",
    "issue"
}

NUMERIC_MEASURE_FIELDS = {
    'technical.fileSize.measure',
    'source.physicalDescription.dataCapacity.measure',
    'source.physicalDescription.conditionFading',
    'source.physicalDescription.conditionScratches',
    'source.physicalDescription.conditionSplices',
    'source.physicalDescription.conditionPerforationDamage',
    'source.physicalDescription.conditionDistortion',
    'source.physicalDescription.shrinkage.measure',
    'source.physicalDescription.acetateDecayLevel',
    'source.contentSpecifications.frameRate.measure',
    'source.contentSpecifications.regionCode',
}

# Fields to force‐into strings (even if they look numeric)
STRING_MEASURE_FIELDS = {
    'digitizationProcess.playbackDevice.phonoCartridge.stylusSize.measure'
}

# Fields where 0 is a valid/required value and should not be dropped
PRESERVE_ZERO_FIELDS = {
    'source.audioRecording.numberOfAudioTracks'
}

# Load other environment variables
database_name = os.getenv('AMI_DATABASE')
username = os.getenv('AMI_DATABASE_USERNAME')
password = os.getenv('AMI_DATABASE_PASSWORD')
jdbc_path = os.path.expanduser('~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar')


# Define the convert_mixed_types function
def convert_mixed_types(value):
    """
    Convert value to a float or integer if possible, otherwise return the original string.
    Preserve fractional numbers by converting to float and convert to integer only if the number is whole.
    """
    try:
        float_value = float(value)
        # If the float value is equivalent to an int, return it as int to avoid unnecessary decimal points.
        if float_value.is_integer():
            return int(float_value)
        else:
            return float_value
    except ValueError:
        return value

def connect_to_database(server_ip: str) -> jaydebeapi.Connection:
    url = f'jdbc:filemaker://{server_ip}/{database_name}'
    try:
        conn = jaydebeapi.connect('com.filemaker.jdbc.Driver', url,
                                  [username, password],
                                  jdbc_path)
        logging.info(f"Connected to FileMaker at {server_ip}")
        return conn
    except Exception as e:
        logging.error(f"DB connection failed: {e}")
        return None

# Parse filename components
def parse_filename(filename):
    """Parse filename to extract base identifier, version, face, region/stream, role, and extension."""
    stem = Path(filename).stem
    ext = Path(filename).suffix.lower()
    
    # Pattern to match: identifier_version[face][region/stream]_role
    # Examples: 
    # - myd_123456_v01_pm, myd_123456_v01f01_pm, myd_123456_v01f01r02_sc
    # - scb_999999_v01f01s01_pm (multitrack audio with stream)
    
    # Updated pattern to handle both regions (r##) and streams (s##)
    pattern = r'^(.+_v\d+)(f\d+)?([rs]\d+)?_([a-z]+)$'
    match = re.match(pattern, stem)
    
    if match:
        base_id = match.group(1)     # e.g., "scb_999999_v01"
        face = match.group(2)        # e.g., "f01" or None
        region_or_stream = match.group(3)  # e.g., "r02", "s01" or None
        role = match.group(4)        # e.g., "pm", "sc", "em", "mz"
        
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
            'role': role,
            'extension': ext,
            'full_stem': stem,
            'filename': filename,
            'is_multitrack': stream is not None
        }
    
    # Fallback for DVD-style filenames (backwards compatibility)
    if '_pm' in stem and ext == '.iso':
        base_id = stem.replace('_pm', '')
        return {
            'base_id': base_id,
            'face': None,
            'region': None,
            'stream': None,
            'role': 'pm',
            'extension': ext,
            'full_stem': stem,
            'filename': filename,
            'is_multitrack': False
        }
    elif ext == '.mp4' and ('f' in stem and 'r' in stem):
        # DVD MP4 with face/region
        mp4_key = stem.split('f')[0]
        return {
            'base_id': mp4_key,
            'face': 'f' + stem.split('f')[1].split('r')[0] if 'f' in stem else None,
            'region': 'r' + stem.split('r')[1].split('_')[0] if 'r' in stem else None,
            'stream': None,
            'role': 'sc',
            'extension': ext,
            'full_stem': stem,
            'filename': filename,
            'is_multitrack': False
        }
    elif ext == '.mp4' and stem.endswith('_sc'):
        # DVD MP4 service copy
        base_id = stem[:-3].rstrip('_')
        return {
            'base_id': base_id,
            'face': None,
            'region': None,
            'stream': None,
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

def export_json_for_file(conn, media_file: Path, output_root: Path):
    parsed = parse_filename(media_file.name)
    if not parsed:
        logging.warning(f"Could not parse {media_file.name}; skipping")
        return
    
    # 0) figure out media_type right up front
    media_type = 'video' if parsed['extension'] in VIDEO_EXTENSIONS else 'audio'
    is_iso     = (parsed['extension'] == '.iso')

    role = parsed['role']
    refname = parsed['filename']  # e.g. "mym_531986_v01f01_pm.wav"
    record = fetch_original_record(conn, refname)

    # 2) if it’s a FLAC and we found nothing, retry with WAV
    if record is None and parsed['extension'] == '.flac':
        wav_name = Path(refname).with_suffix('.wav').name
        logging.info(f"No FM record for {refname}; retrying with {wav_name}")
        record = fetch_original_record(conn, wav_name)
    
    if record is None:
        logging.error(f"No FileMaker record for {refname} (or its .wav equivalent); skipping")
        return

    # Build nested JSON object
    nested = {}
    for col, val in record.items():
        # 1) drop asset.fileExt entirely 
        if col == 'asset.fileExt':
            continue

        # 2) if ISO and this is the capacity field, override None→'unknown'
        if is_iso and col == 'source.physicalDescription.dataCapacity.measure':
            if val is None:
                val = 'unknown'

        # 2a) only for grooved‐disc/cylinder AND matching unit, default measure None→0
        obj_type = record.get('source.object.type')
        if obj_type in ('audio grooved disc', 'audio grooved cylinder'):
            # eqRolloff: measure key + check unit == 'dB'
            if col == 'digitizationProcess.phonoPreamp.eqRolloff.measure':
                unit = record.get('digitizationProcess.phonoPreamp.eqRolloff.unit')
                if unit == 'dB' and val is None:
                    val = 0
            # eqTurnover: measure key + check unit == 'Hz'
            elif col == 'digitizationProcess.phonoPreamp.eqTurnover.measure':
                unit = record.get('digitizationProcess.phonoPreamp.eqTurnover.unit')
                if unit == 'Hz' and val is None:
                    val = 0

        # 3) skip any blank or NULL value
        if val is None or val == '':
            continue

        # 4) for an audio file, drop zero‐track entries only
        if (
            media_type == 'audio' and
            col == 'source.audioRecording.numberOfAudioTracks' and
            val == 0
        ):
            continue

        # 5) force real numbers where your schema wants numbers
        if col in NUMERIC_MEASURE_FIELDS:
            val = convert_mixed_types(val)

        # 6) force string where your schema wants a string
        elif col in STRING_MEASURE_FIELDS:
            val = str(val)

        # 7) everything else…
        nested = convert_dotKeyToNestedDict(nested, col, val)

    # ---- drop just digitizationProcess.playbackDevice.id ----
    pdp = nested.get('digitizationProcess', {}).get('playbackDevice', {})
    pdp.pop('id', None)

    # drop timeBaseCorrector.id
    tbc = nested.get('digitizationProcess', {}).get('timeBaseCorrector', {})
    tbc.pop('id', None)

    # ---- NEW: prune out any unwanted top-level keys ----
    clean = {k: v for k, v in nested.items() if k not in DROP_TOP_LEVEL}

    # Write it out
    dest_dir = output_root / ROLE_DIRS.get(role, 'other')
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / f"{media_file.stem}.json"
    with open(out_path, 'w') as fp:
        json.dump(clean, fp, indent=4)
    logging.info(f"Wrote JSON for {refname} → {out_path}")

def convert_dotKeyToNestedDict(tree: dict, key: str, value) -> dict:
    """
    Convert a dot-delimited key and its corresponding value to a nested dictionary, excluding keys with empty values.
    Args:
        tree: The dictionary to add the key-value pair to.
        key: The dot-delimited key string.
        value: The value associated with the key.
    Returns:
        The updated dictionary with the key-value pair added, excluding keys with empty values.
    """

    if "." in key:
        # Split the key by the first dot and recursively call the function
        # on the first part of the key with the rest of the key and the value
        # as arguments.
        first_key, remaining_keys = key.split(".", 1)
        if first_key not in tree:
            tree[first_key] = {}
        convert_dotKeyToNestedDict(tree[first_key], remaining_keys, value)
    else:
        # Base case: add the key-value pair to the dictionary.
        tree[key] = value

    return tree

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
            
            for col, value in zip(columns, record):
                if value is None or value == '':
                    record_dict[col] = None
                elif isinstance(value, float):
                    # FIXED: Don't drop 0.0 for fields that require zero values
                    if value == 0.0 and col not in PRESERVE_ZERO_FIELDS:
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

def main():
    parser = argparse.ArgumentParser(
        description="Fetch FileMaker records by filename and emit record‐level JSON"
    )
    parser.add_argument('-d','--directory', required=True,
                        help="Root folder containing your PM/EM/SC/MZ subdirs")
    parser.add_argument('-o','--output', required=True,
                        help="Where to write the JSON files")
    parser.add_argument('--dev-server', action='store_true',
                        help="Use dev instead of prod credentials")
    args = parser.parse_args()

    server_ip = os.getenv('FM_DEV_SERVER') if args.dev_server else os.getenv('FM_SERVER')
    conn = connect_to_database(server_ip)

    data_root   = Path(args.directory)
    output_root = Path(args.output)
    json_count  = 0

    # 2) Crawl for all media files
    media_files = [p for p in data_root.rglob('*') if p.suffix.lower() in ALL_MEDIA_EXTENSIONS]
    for media_file in media_files:
        export_json_for_file(conn, media_file, output_root)

    conn.close()
    logging.info(f"\nDone: exported {json_count} JSON files.")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    main()