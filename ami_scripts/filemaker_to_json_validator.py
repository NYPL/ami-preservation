#!/usr/bin/env python3
"""
FileMaker to JSON export script
Exports media file metadata from FileMaker to structured JSON files.
"""
import os
import json
import jaydebeapi
import logging
from pathlib import Path
from collections import defaultdict
import argparse
import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Union
import pandas as pd
import subprocess
import shutil
from collections import Counter


# =============================================================================
# CONFIGURATION AND CONSTANTS
# =============================================================================

@dataclass
class Config:
    """Centralized configuration management."""
    database_name: str
    username: str
    password: str
    jdbc_path: str
    server_ip: str
    
    @classmethod
    def from_env(cls, dev_mode: bool = False) -> 'Config':
        """Create config from environment variables."""
        server_key = 'FM_DEV_SERVER' if dev_mode else 'FM_SERVER'
        
        required_vars = {
            'database_name': 'AMI_DATABASE',
            'username': 'AMI_DATABASE_USERNAME', 
            'password': 'AMI_DATABASE_PASSWORD',
            'server_ip': server_key
        }
        
        config_values = {}
        for attr, env_var in required_vars.items():
            value = os.getenv(env_var)
            if not value:
                raise ValueError(f"Required environment variable {env_var} not set")
            config_values[attr] = value
        
        # Default JDBC path
        jdbc_path = os.path.expanduser('~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar')
        config_values['jdbc_path'] = jdbc_path
        
        return cls(**config_values)


class MediaFormats:
    """Media format definitions and extensions."""
    VIDEO_EXTENSIONS = {'.mkv', '.mov', '.mp4', '.dv', '.iso'}
    AUDIO_EXTENSIONS = {'.wav', '.flac', '.aea'}
    ALL_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


class DirectoryStructure:
    """Directory structure mappings."""
    ROLE_DIRS = {
        'pm': 'PreservationMasters',
        'em': 'EditMasters', 
        'sc': 'ServiceCopies',
        'mz': 'Mezzanines',
    }


class FieldRules:
    """Field processing rules and transformations."""
    
    # Fields to drop entirely from top-level JSON
    DROP_TOP_LEVEL = {
        "Archival box number", "Archival box barcode", "__zkill_workorder", "id",
        "__creationTimestamp", "_md_dp", "_md_s", "_md_t", "WorkOrderID",
        "__modificationTimestamp", "__modificationUser", "cmsCollectionTitle",
        "bibliographic_primaryID", "uk_1", "projectType", "zkill_digitizationProcess",
        "ref_ami_files_record_id", "cmsCollectionRepository", "__migrationExceptions",
        "__captureIssueCategory", "__captureIssueNote", "MARK", "issue"
    }
    
    # Fields to convert to numeric types
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
    
    # Fields to force into strings
    STRING_MEASURE_FIELDS = {
        'digitizationProcess.playbackDevice.phonoCartridge.stylusSize.measure'
    }
    
    # Fields where 0 is valid and should not be dropped
    PRESERVE_ZERO_FIELDS = {
        'source.audioRecording.numberOfAudioTracks'
    }
    
    # Fields that should always be strings
    ALWAYS_STRING_FIELDS = {
        'asset.schemaVersion', 
        'bibliographic.barcode'
    }


# =============================================================================
# FILENAME PARSING
# =============================================================================

class FilenameParser:
    """Handles parsing of media filenames into components."""
    
    @staticmethod
    def parse_filename(filename: str) -> Optional[Dict[str, Any]]:
        """
        Parse filename to extract base identifier, version, face, region/stream, take, role, and extension.
        
        Examples:
        - myd_123456_v01_pm, myd_123456_v01f01_pm, myd_123456_v01f01r02_sc
        - scb_999999_v01f01s01_pm (multitrack audio with stream)
        - myh_666666_v01f01t01_pm (with take)
        - myh_666666_v01f01r01t01_pm (with region and take)
        """
        stem = Path(filename).stem
        ext = Path(filename).suffix.lower()
        
        # Primary pattern: identifier_version[face][region/stream][take]_role
        pattern = r'^(.+_v\d+)(f\d+)?([rs]\d+)?(t\d+)?_([a-z]+)$'
        match = re.match(pattern, stem)
        
        if match:
            return FilenameParser._build_parsed_result(match, ext, stem, filename)
        
        # Fallback patterns for DVD-style filenames
        return FilenameParser._parse_dvd_fallback(stem, ext, filename)
    
    @staticmethod
    def _build_parsed_result(match, ext: str, stem: str, filename: str) -> Dict[str, Any]:
        """Build parsed result from regex match."""
        base_id = match.group(1)
        face = match.group(2)
        region_or_stream = match.group(3)
        take = match.group(4)   
        role = match.group(5)    
        
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
            'take': take,  # <-- NEW
            'role': role,
            'extension': ext,
            'full_stem': stem,
            'filename': filename,
            'is_multitrack': stream is not None
        }
    
    @staticmethod
    def _parse_dvd_fallback(stem: str, ext: str, filename: str) -> Optional[Dict[str, Any]]:
        """Handle DVD-style filename patterns."""
        base_result = {
            'extension': ext,
            'full_stem': stem,
            'filename': filename,
            'is_multitrack': False,
            'take': None  # 
        }
        
        # DVD ISO preservation master
        if '_pm' in stem and ext == '.iso':
            base_result.update({
                'base_id': stem.replace('_pm', ''),
                'face': None,
                'region': None,
                'stream': None,
                'role': 'pm'
            })
            return base_result
        
        # DVD MP4 with face/region
        elif ext == '.mp4' and ('f' in stem and 'r' in stem):
            mp4_key = stem.split('f')[0]
            face = 'f' + stem.split('f')[1].split('r')[0] if 'f' in stem else None
            region = 'r' + stem.split('r')[1].split('_')[0] if 'r' in stem else None
            
            base_result.update({
                'base_id': mp4_key,
                'face': face,
                'region': region,
                'stream': None,
                'role': 'sc'
            })
            return base_result
        
        # DVD MP4 service copy
        elif ext == '.mp4' and stem.endswith('_sc'):
            base_result.update({
                'base_id': stem[:-3].rstrip('_'),
                'face': None,
                'region': None,
                'stream': None,
                'role': 'sc'
            })
            return base_result
        
        return None


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

class FileMakerClient:
    """Handles FileMaker database connections and queries."""
    
    def __init__(self, config: Config):
        self.config = config
        self.connection = None
        
    def connect(self) -> bool:
        """Establish database connection."""
        url = f'jdbc:filemaker://{self.config.server_ip}/{self.config.database_name}'
        try:
            self.connection = jaydebeapi.connect(
                'com.filemaker.jdbc.Driver', 
                url,
                [self.config.username, self.config.password],
                self.config.jdbc_path
            )
            logging.info(f"Connected to FileMaker at {self.config.server_ip}")
            return True
        except Exception as e:
            logging.error(f"DB connection failed: {e}")
            return False
    
    def fetch_record(self, reference_filename: str) -> Optional[Dict[str, Any]]:
        """
        Fetch record by reference filename, with FLAC->WAV fallback logic.
        Preserves all original null handling and type conversion logic.
        """
        if not self.connection:
            logging.error("No database connection")
            return None
            
        # Try original filename first
        record = self._fetch_single_record(reference_filename)
        
        # If FLAC file and no record found, try WAV equivalent
        if record is None and reference_filename.lower().endswith('.flac'):
            wav_name = Path(reference_filename).with_suffix('.wav').name
            logging.info(f"No FM record for {reference_filename}; retrying with {wav_name}")
            record = self._fetch_single_record(wav_name)
        
        return record
    
    def _fetch_single_record(self, reference_filename: str) -> Optional[Dict[str, Any]]:
        """Fetch a single record from FileMaker."""
        cursor = self.connection.cursor()
        try:
            query = 'SELECT * FROM tbl_metadata WHERE "asset.referenceFilename" = ?'
            logging.debug(f"Fetching record with asset.referenceFilename = {reference_filename}")
            cursor.execute(query, [reference_filename])
            
            record = cursor.fetchone()
            if not record:
                logging.warning(f"No record found for {reference_filename}")
                return None
            
            return self._process_record(cursor, record)
            
        except Exception as e:
            logging.error(f"Error fetching record for {reference_filename}: {e}")
            return None
        finally:
            cursor.close()
    
    def _process_record(self, cursor, record) -> Dict[str, Any]:
        """Process raw database record with proper type handling."""
        columns = [desc[0] for desc in cursor.description]
        record_dict = {}
        
        for col, value in zip(columns, record):
            # Handle None and empty string values
            if value is None or value == '':
                record_dict[col] = None
                continue
            
            # Handle float values with special zero preservation logic
            if isinstance(value, float):
                # CRITICAL: Don't drop 0.0 for fields that require zero values
                if value == 0.0 and col not in FieldRules.PRESERVE_ZERO_FIELDS:
                    record_dict[col] = None
                elif value.is_integer():
                    record_dict[col] = int(value)
                else:
                    record_dict[col] = value
            else:
                record_dict[col] = value
        
        # Ensure specific fields are always strings
        for field in FieldRules.ALWAYS_STRING_FIELDS:
            if field in record_dict and record_dict[field] is not None:
                record_dict[field] = str(record_dict[field])
        
        return record_dict
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None


# =============================================================================
# DATA TRANSFORMATION
# =============================================================================

class DataTransformer:
    """Handles data transformation and JSON structure building."""
    
    @staticmethod
    def convert_mixed_types(value: Any) -> Union[int, float, str]:
        """
        Convert value to a float or integer if possible, otherwise return the original string.
        Preserve fractional numbers by converting to float and convert to integer only if whole.
        """
        try:
            float_value = float(value)
            if float_value.is_integer():
                return int(float_value)
            else:
                return float_value
        except ValueError:
            return value
    
    def transform_record(self, record: Dict[str, Any], media_type: str, 
                        is_iso: bool) -> Dict[str, Any]:
        """Apply all transformation rules to a FileMaker record."""
        if not record:
            return {}
        
        # Build nested structure while applying transformations
        nested = {}
        obj_type = record.get('source.object.type')
        
        for col, val in record.items():
            # Apply field-specific transformations
            val = self._apply_field_transformations(col, val, media_type, is_iso, obj_type, record)
            
            # Skip if value should be filtered out
            if self._should_skip_field(col, val, media_type):
                continue
            
            # Convert to nested structure
            nested = self._convert_dot_key_to_nested(nested, col, val)
        
        # Clean up nested structure
        return self._cleanup_nested_structure(nested)
    
    def _apply_field_transformations(self, col: str, val: Any, media_type: str, 
                                    is_iso: bool, obj_type: str, record: Dict[str, Any]) -> Any:
            """Apply all field-specific transformations."""
            # Drop asset.fileExt entirely
            if col == 'asset.fileExt':
                return None
            
            # Skip None/empty values early, except for special cases
            if val is None or val == '':
                # ISO capacity field override
                # CHANGE: Check if it is an ISO OR if the object type is video optical disc
                if col == 'source.physicalDescription.dataCapacity.measure':
                    if is_iso or obj_type == 'video optical disc':
                        return 'unknown'
                
                # Grooved disc/cylinder specific defaults for None values
                if obj_type in ('audio grooved disc', 'audio grooved cylinder'):
                    # eqRolloff: measure key + check unit == 'dB'
                    if col == 'digitizationProcess.phonoPreamp.eqRolloff.measure':
                        unit = record.get('digitizationProcess.phonoPreamp.eqRolloff.unit')
                        if unit == 'dB':
                            return 0
                    # eqTurnover: measure key + check unit == 'Hz'
                    elif col == 'digitizationProcess.phonoPreamp.eqTurnover.measure':
                        unit = record.get('digitizationProcess.phonoPreamp.eqTurnover.unit')
                        if unit == 'Hz':
                            return 0
                
                return None
            
            # Type conversions (only for non-None values)
            if col in FieldRules.NUMERIC_MEASURE_FIELDS:
                val = self.convert_mixed_types(val)
            elif col in FieldRules.STRING_MEASURE_FIELDS:
                val = str(val)
            
            return val
    
    def _handle_grooved_disc_fields(self, col: str, val: Any, record: Dict) -> Any:
        """Handle special grooved disc/cylinder field defaults."""
        # This method is now integrated into _apply_field_transformations
        # Keeping for potential future use
        return val
    
    def _should_skip_field(self, col: str, val: Any, media_type: str) -> bool:
        """Determine if a field should be skipped."""
        # Skip None or empty values
        if val is None or val == '':
            return True
        
        # For audio files, skip zero track entries
        if (media_type == 'audio' and 
            col == 'source.audioRecording.numberOfAudioTracks' and 
            val == 0):
            return True
        
        return False
    
    def _convert_dot_key_to_nested(self, tree: Dict, key: str, value: Any) -> Dict:
        """Convert dot-delimited key to nested dictionary structure."""
        if "." in key:
            first_key, remaining_keys = key.split(".", 1)
            if first_key not in tree:
                tree[first_key] = {}
            self._convert_dot_key_to_nested(tree[first_key], remaining_keys, value)
        else:
            tree[key] = value
        return tree
    
    def _cleanup_nested_structure(self, nested: Dict) -> Dict:
        """Clean up nested structure by removing unwanted fields."""
        # Remove specific nested IDs
        if 'digitizationProcess' in nested:
            dp = nested['digitizationProcess']
            
            # Remove playbackDevice.id
            if 'playbackDevice' in dp:
                dp['playbackDevice'].pop('id', None)
            
            # Remove timeBaseCorrector.id  
            if 'timeBaseCorrector' in dp:
                dp['timeBaseCorrector'].pop('id', None)
        
        # Remove top-level unwanted fields
        return {k: v for k, v in nested.items() if k not in FieldRules.DROP_TOP_LEVEL}


# =============================================================================
# FILE PROCESSING
# =============================================================================

class FileProcessor:
    """Handles file discovery and processing orchestration."""
    
    def __init__(self, db_client: FileMakerClient, transformer: DataTransformer):
        self.db_client = db_client
        self.transformer = transformer
    
    def crawl_directory(self, directory: Path) -> Dict[str, Dict]:
        """Crawl directory recursively and organize files by media type and base identifier."""
        file_groups = defaultdict(lambda: {'pm_files': [], 'derivative_files': []})
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                filepath = Path(root) / file
                if filepath.suffix.lower() in MediaFormats.ALL_EXTENSIONS:
                    parsed = FilenameParser.parse_filename(file)
                    if parsed:
                        base_id = parsed['base_id']
                        media_type = ('video' if parsed['extension'] in MediaFormats.VIDEO_EXTENSIONS 
                                    else 'audio')
                        
                        file_info = {
                            'path': filepath,
                            'parsed': parsed,
                            'media_type': media_type
                        }
                        
                        if parsed['role'] == 'pm':
                            file_groups[base_id]['pm_files'].append(file_info)
                        else:
                            file_groups[base_id]['derivative_files'].append(file_info)
                        
                        logging.debug(f"Parsed {file}: {parsed}")
        
        result = dict(file_groups)
        logging.info(f"Found {len(result)} file groups")
        for base_id, group in result.items():
            pm_count = len(group['pm_files'])
            deriv_count = len(group['derivative_files'])
            logging.info(f"  {base_id}: {pm_count} PM files, {deriv_count} derivative files")
        
        return result
    
    def export_json_for_file(self, media_file: Path, output_root: Path) -> bool:
        """Export JSON for a single media file."""
        parsed = FilenameParser.parse_filename(media_file.name)
        if not parsed:
            logging.warning(f"Could not parse {media_file.name}; skipping")
            return False
        
        # Determine media type and special characteristics
        media_type = 'video' if parsed['extension'] in MediaFormats.VIDEO_EXTENSIONS else 'audio'
        is_iso = (parsed['extension'] == '.iso')
        role = parsed['role']
        refname = parsed['filename']
        
        # Fetch and transform record
        record = self.db_client.fetch_record(refname)
        if record is None:
            logging.error(f"No FileMaker record for {refname}; skipping")
            return False
        
        # Transform record to JSON structure
        json_data = self.transformer.transform_record(record, media_type, is_iso)
        
        # Write JSON file
        return self._write_json_file(json_data, media_file, output_root, role)
    
    def _write_json_file(self, json_data: Dict, media_file: Path, 
                        output_root: Path, role: str) -> bool:
        """Write JSON data to file."""
        try:
            dest_dir = output_root / DirectoryStructure.ROLE_DIRS.get(role, 'other')
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            out_path = dest_dir / f"{media_file.stem}.json"
            with open(out_path, 'w') as fp:
                json.dump(json_data, fp, indent=4)
            
            logging.info(f"Wrote JSON for {media_file.name} → {out_path}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to write JSON for {media_file.name}: {e}")
            return False


# =============================================================================
# MAIN APPLICATION
# =============================================================================

def get_info(source_directory: Union[str, Path], metadata_directory: Union[str, Path]) -> None:
    """
    Count JSON files by object type, validate them via AJV, 
    and—if any fail—move all JSONs into an InvalidJSON folder.
    """
    source_dir = Path(source_directory)
    metadata_dir = Path(metadata_directory)
    schema_dir = metadata_dir / 'versions' / '2.0' / 'schema'

    # Gather
    json_files = sorted(source_dir.rglob('*.json'))
    logging.info("Found %d JSON files for inspection", len(json_files))

    # Count by type
    type_counts: Counter = Counter()
    for json_path in json_files:
        try:
            data = json.loads(json_path.read_text())
            obj_type = data.get('source', {}) \
                           .get('object', {}) \
                           .get('type', 'Unknown')
            type_counts[obj_type] += 1
        except Exception as e:
            logging.warning("Could not read %s: %s", json_path, e)
    logging.info("JSON files by object type: %s", dict(type_counts))

    # Validate
    valid_count = invalid_count = 0
    for json_path in json_files:
        try:
            data = json.loads(json_path.read_text())
            ajv_cmd = get_ajv_command(data, str(json_path))
            result = subprocess.run(
                ajv_cmd,
                cwd=schema_dir,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                valid_count += 1
            else:
                invalid_count += 1
                logging.error(
                    "Validation failed for %s:\n%s",
                    json_path,
                    result.stderr or result.stdout
                )

        except Exception as e:
            invalid_count += 1
            logging.error("Error validating %s: %s", json_path, e)

    logging.info("Validation summary: %d valid, %d invalid", valid_count, invalid_count)

    # If any invalid, move all JSONs into an “InvalidJSON” folder
    if invalid_count > 0:
        invalid_dir = source_dir / 'InvalidJSON'
        invalid_dir.mkdir(parents=True, exist_ok=True)
        for json_path in json_files:
            dest = invalid_dir / json_path.name
            try:
                shutil.move(str(json_path), str(dest))
                logging.debug("Moved %s → %s", json_path, dest)
            except Exception as e:
                logging.error("Failed to move %s to %s: %s", json_path, invalid_dir, e)
        logging.info(
            "Moved all JSON files into '%s' due to one or more validation failures",
            invalid_dir
        )

def get_ajv_command(data, file):
    object_type = data['source']['object']['type']
    object_format = data['source']['object']['format']

    schema_mapping = {
        'video cassette analog': 'digitized_videocassetteanalog.json',
        'video cassette digital': 'digitized_videocassettedigital.json',
        'video reel': 'digitized_videoreel.json',
        'video optical disc': 'digitized_videoopticaldisc.json',
        'audio cassette analog': 'digitized_audiocassetteanalog.json',
        'audio reel analog': 'digitized_audioreelanalog.json',
        'audio cassette digital': 'digitized_audiocassettedigital.json',
        'audio reel digital': 'digitized_audioreeldigital.json',
        'audio optical disc': 'digitized_audioopticaldisc.json',
        'audio grooved disc': 'digitized_audiogrooveddisc.json',
        'audio grooved cylinder': 'digitized_audiogroovedcylinder.json',
        'audio magnetic wire': 'digitized_audiomagneticwire.json',
        'data optical disc': 'digitized_dataopticaldisc.json',
    }

    film_formats = ('8mm film, silent', '8mm film, optical sound',
                    '8mm film, magnetic sound', 'Super 8 film, silent',
                    'Super 8 film, optical sound', 'Super 8 film, magnetic sound',
                    '16mm film, silent', '16mm film, optical sound', '16mm film, magnetic sound',
                    '35mm film, silent', '35mm film, optical sound', '35mm film, magnetic sound',
                    '9.5mm film, silent', 'Double 8mm film, silent')

    audio_film_formats = ('16mm film, optical track', '16mm film, full-coat magnetic sound',
                          '35mm film, optical track', '35mm film, full-coat magnetic sound')

    if object_type in schema_mapping:
        schema_file = schema_mapping[object_type]
    elif object_format in film_formats:
        schema_file = 'digitized_motionpicturefilm.json'
    elif object_format in audio_film_formats:
        schema_file = 'digitized_audiofilm.json'
    else:
        raise ValueError(f"Unknown object type or format: {object_type}, {object_format}")

    ajv_command = [
        'ajv',
        'validate',
        '-s',
        f'../schema/{schema_file}',
        '-r',
        '../schema/fields.json',
        '-d', file,
        '--all-errors',
        '--errors=json'
    ]
    return ajv_command

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main():
    """Main application entry point."""
    # ——— CLI arguments ———
    parser = argparse.ArgumentParser(
        description="Fetch FileMaker records by filename and emit record-level JSON"
    )
    parser.add_argument('-d', '--directory', required=True,
                        help="Root folder containing your PM/EM/SC/MZ subdirs")
    parser.add_argument('-o', '--output', required=True,
                        help="Where to write the JSON files")
    parser.add_argument('--dev-server', action='store_true',
                        help="Use dev instead of prod credentials")
    parser.add_argument('--verbose', '-v', action='store_true',
                        help="Enable verbose logging")

    # validation is ON by default; use --skip-json-validation to disable
    parser.add_argument(
        '--skip-json-validation',
        dest='validate_json',
        action='store_false',
        help="Disable AJV validation of the exported JSON (enabled by default)"
    )
    parser.set_defaults(validate_json=True)

    parser.add_argument(
        '--metadata-dir', '-m',
        help="Path to your schema directory parent (e.g. versions/2.0/schema parent dir)"
    )

    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize configuration
        config = Config.from_env(args.dev_server)
        
        # Initialize components
        db_client = FileMakerClient(config)
        transformer = DataTransformer()
        processor = FileProcessor(db_client, transformer)
        
        # Connect to database
        if not db_client.connect():
            logging.error("Failed to connect to database")
            return 1
        
        # Process files
        data_root = Path(args.directory)
        output_root = Path(args.output)
        
        # Find all media files
        media_files = [
            p for p in data_root.rglob('*') 
            if p.suffix.lower() in MediaFormats.ALL_EXTENSIONS
        ]
        
        logging.info(f"Found {len(media_files)} media files to process")
        
        # Process each file
        success_count = 0
        for media_file in media_files:
            if processor.export_json_for_file(media_file, output_root):
                success_count += 1
        
        logging.info(f"Successfully exported {success_count}/{len(media_files)} JSON files")

        # ——— JSON VALIDATION STEP ———
        if args.validate_json:
            if not args.metadata_dir:
                logging.error("`-m` or `--metadata-dir` is required when JSON validation is enabled")
                return 1
            get_info(str(output_root), args.metadata_dir)

        return 0
                
    except Exception as e:
        logging.error(f"Application error: {e}")
        return 1
    
    finally:
        if 'db_client' in locals():
            db_client.close()


if __name__ == '__main__':
    exit(main())