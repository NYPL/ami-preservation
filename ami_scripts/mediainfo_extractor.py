#!/usr/bin/env python3
"""
Media Information Extraction Tool

This script extracts technical metadata from video and audio files using MediaInfo
and ffprobe, with support for BagIt bag processing and vendor JSON sidecars.
Output can be either CSV files or direct database insertion via JDBC.
"""

import argparse
import csv
import json
import logging
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

import jaydebeapi
from pymediainfo import MediaInfo


# Configuration constants
VIDEO_EXTENSIONS: Set[str] = {'.mkv', '.mov', '.mp4', '.dv', '.iso'}
AUDIO_EXTENSIONS: Set[str] = {'.wav', '.flac', '.aea'}
BAGIT_REQUIRED_FILES: Set[str] = {'bag-info.txt', 'bagit.txt', 'manifest-md5.txt', 'tagmanifest-md5.txt'}

# JDBC field mapping for database insertion
JDBC_FIELDS: List[str] = [
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

# Complete field mapping for CSV output
CSV_FIELD_NAMES: List[str] = [
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

CSV_HEADERS: List[str] = [
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
    'source.object.format',
    'inhouse_bag_batch_id'
]


def setup_logging() -> None:
    """Configure logging with consistent format."""
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract MediaInfo from video and audio files"
    )
    parser.add_argument(
        "-d", "--directory",
        help="Path to folder containing media files",
        required=False
    )
    parser.add_argument(
        "-f", "--file", 
        help="Path to individual media file",
        required=False
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to save CSV output file"
    )
    parser.add_argument(
        "-v", "--vendor", 
        action='store_true',
        help="Process as BagIt with sidecar JSON metadata"
    )
    return parser


class BagItProcessor:
    """Handle BagIt bag detection and processing."""
    
    @staticmethod
    def is_bag(directory: Path) -> bool:
        """Check if directory is a valid BagIt bag."""
        existing_files = {file.name for file in directory.iterdir() if file.is_file()}
        return BAGIT_REQUIRED_FILES <= existing_files

    @classmethod
    def find_bags(cls, top_directory: Path) -> List[Path]:
        """Find all BagIt bags in the top directory."""
        bags = []
        for directory in top_directory.iterdir():
            if directory.is_dir() and cls.is_bag(directory):
                bags.append(directory)
                logging.info(f"Identified BagIt bag: {directory}")
        return bags

    @staticmethod
    def get_media_files_from_bag(bag_directory: Path) -> List[Path]:
        """Extract media files from a BagIt bag's data directory."""
        valid_extensions = VIDEO_EXTENSIONS.union(AUDIO_EXTENSIONS)
        media_files = []
        
        data_directory = bag_directory / "data"
        if not data_directory.exists():
            return media_files
            
        for path in data_directory.rglob('*'):
            if path.is_file() and path.suffix.lower() in valid_extensions:
                if path.name.startswith("._"):
                    logging.info(f"Skipping hidden Mac file: {path}")
                else:
                    media_files.append(path)
                    logging.info(f"Adding file to processing list: {path}")
        
        return media_files


class JSONSidecarProcessor:
    """Handle JSON sidecar file processing."""
    
    @staticmethod
    def read_sidecar(json_path: Path) -> Dict[str, Optional[str]]:
        """Read and parse JSON sidecar file."""
        try:
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
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.error(f"Error reading JSON sidecar {json_path}: {e}")
            return {'collectionID': None, 'objectType': None, 'objectFormat': None}


class MediaAnalyzer:
    """Handle media file analysis and metadata extraction."""
    
    @staticmethod
    def has_mezzanines_folder(file_path: Path) -> bool:
        """Check if file has a Mezzanines folder in its hierarchy."""
        for parent in file_path.parents:
            mezzanines_dir = parent / "Mezzanines"
            if mezzanines_dir.is_dir():
                return True
        return False

    @staticmethod
    def extract_iso_file_format(file_path: Path) -> Optional[str]:
        """Extract file format from ISO files using isolyzer."""
        command = ['isolyzer', str(file_path)]
        try:
            process = subprocess.run(
                command, 
                check=True, 
                capture_output=True, 
                text=True
            )
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

    @staticmethod
    def extract_with_ffprobe(path: Path) -> Dict[str, Union[int, float, str, None]]:
        """Use ffprobe to extract basic media information."""
        cmd = [
            'ffprobe', '-v', 'error',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(path)
        ]
        
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(proc.stdout)
            info = data.get('format', {})
            streams = data.get('streams', [])

            # Extract basic information
            size = int(info.get('size', 0))
            duration_s = float(info.get('duration', 0.0))
            fmt_name = info.get('format_name')
            
            # Find audio and video codecs
            audio_codec = next(
                (s['codec_name'] for s in streams if s.get('codec_type') == 'audio'), 
                None
            )
            video_codec = next(
                (s['codec_name'] for s in streams if s.get('codec_type') == 'video'), 
                None
            )

            # Format duration as HH:MM:SS.mmm
            human_dur = MediaAnalyzer._format_duration(duration_s)

            # Get file modification date
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
            
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logging.error(f"ffprobe failed for {path}: {e}")
            return {
                'file_size': 0,
                'duration_s': 0.0,
                'human_duration': '00:00:00.000',
                'file_format': None,
                'audio_codec': None,
                'video_codec': None,
                'date_created': datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d'),
            }

    @staticmethod
    def _format_duration(duration_s: float) -> str:
        """Format duration in seconds to HH:MM:SS.mmm format."""
        hrs = int(duration_s // 3600)
        rem = duration_s - hrs * 3600
        mins = int(rem // 60)
        rem2 = rem - mins * 60
        secs = int(rem2)
        ms = int(round((rem2 - secs) * 1000))
        
        # Handle rounding overflow
        if ms == 1000:
            secs += 1
            ms = 0
            if secs == 60:
                mins += 1
                secs = 0
                if mins == 60:
                    hrs += 1
                    mins = 0
                    
        return f"{hrs:02d}:{mins:02d}:{secs:02d}.{ms:03d}"

    @classmethod
    def extract_track_info(cls, media_info: MediaInfo, path: Path) -> Optional[List]:
        """Extract comprehensive track information from media file."""
        suffix = path.suffix.lower()

        # Special handling for .aea (MiniDisc) files
        if suffix == '.aea':
            return cls._process_aea_file(path, suffix)
        
        # Handle other media files using MediaInfo
        return cls._process_general_media_file(media_info, path, suffix)

    @classmethod
    def _process_aea_file(cls, path: Path, suffix: str) -> List:
        """Process .aea (MiniDisc) files using ffprobe."""
        ff = cls.extract_with_ffprobe(path)
        
        file_no_ext = path.stem
        parts = file_no_ext.split('_')
        
        role = parts[-1] if parts else None
        division = parts[0] if parts else None
        driveID = path.parts[2] if len(path.parts) > 2 else None
        primaryID = parts[1] if len(parts) > 1 else None

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
        ]

    @classmethod
    def _process_general_media_file(cls, media_info: MediaInfo, path: Path, suffix: str) -> Optional[List]:
        """Process general media files using MediaInfo."""
        date_pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
        
        for track in media_info.tracks:
            if track.track_type == "General":
                # Handle file format
                file_format = track.format
                if file_format is None and suffix == '.iso':
                    file_format = cls.extract_iso_file_format(path)

                # Extract date created
                date_created = None
                if track.file_last_modification_date:
                    match = date_pattern.search(track.file_last_modification_date)
                    if match:
                        date_created = match.group(0)

                # Extract audio codec
                audio_codec = None
                if track.audio_format_list:
                    # Split by ' / ' to handle formats like "FLAC / FLAC"
                    # and "MPEG Audio" correctly
                    audio_codec = track.audio_format_list.split(' / ')[0]

                # Format human duration
                human_duration = None
                if track.duration and track.other_duration:
                    human_duration = str(track.other_duration[3])

                # Determine media type
                media_type = cls._determine_media_type(path, suffix)

                # Extract file metadata
                file_no_ext = path.stem
                parts = file_no_ext.split('_')
                
                role = parts[-1] if parts else None
                division = parts[0] if parts else None
                driveID = path.parts[2] if len(path.parts) > 2 else None
                primaryID = parts[1] if len(parts) > 1 else None

                return [
                    path,                                        # filePath
                    f"{path.stem}.{path.suffix[1:]}",           # asset.referenceFilename
                    path.stem,                                   # technical.filename
                    path.suffix[1:],                             # technical.extension
                    track.file_size,                             # technical.fileSize.measure
                    date_created,                                # technical.dateCreated
                    file_format,                                 # technical.fileFormat
                    audio_codec,                                 # technical.audioCodec
                    track.codecs_video,                          # technical.videoCodec
                    track.duration,                              # technical.durationMilli.measure
                    human_duration,                              # technical.durationHuman
                    media_type,                                  # mediaType
                    role,                                        # asset.fileRole
                    division,                                    # bibliographic.vernacularDivisionCode
                    driveID,                                     # driveID
                    primaryID,                                   # bibliographic.primaryID
                ]
        
        return None

    @classmethod
    def _determine_media_type(cls, path: Path, suffix: str) -> Optional[str]:
        """Determine the media type based on file extension and folder structure."""
        has_mezzanines_folder = cls.has_mezzanines_folder(path)
        
        if suffix in VIDEO_EXTENSIONS:
            return 'film' if has_mezzanines_folder else 'video'
        elif suffix in AUDIO_EXTENSIONS:
            return 'audio'
        
        return None


class DatabaseManager:
    """Handle database operations and connections."""
    
    def __init__(self):
        self.server_ip = os.getenv('FM_SERVER')
        self.database_name = os.getenv('AMI_DATABASE') 
        self.username = os.getenv('AMI_DATABASE_USERNAME')
        self.password = os.getenv('AMI_DATABASE_PASSWORD')
        self.jdbc_path = os.path.expanduser('~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar')

    def filter_for_jdbc(self, record: Dict) -> Dict:
        """Filter record to include only JDBC-compatible fields."""
        return {k: record[k] for k in JDBC_FIELDS if k in record}

    def connect(self):
        """Establish database connection."""
        return jaydebeapi.connect(
            'com.filemaker.jdbc.Driver',
            f'jdbc:filemaker://{self.server_ip}/{self.database_name}',
            [self.username, self.password],
            self.jdbc_path
        )

    def insert_records(self, conn, insert_data: List[Dict]) -> None:
        """Insert records into the database."""
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
            raise

    def check_corresponding_records(self, conn, filenames: List[str]) -> Tuple[int, int]:
        """Check for corresponding records in the production table."""
        curs = conn.cursor()
        found, not_found = 0, 0
        
        logging.info(f"Checking for corresponding records for {len(filenames)} media files in the PRODUCTION table.")
        
        for filename in filenames:
            curs.execute(
                'SELECT COUNT(*) FROM tbl_metadata WHERE "asset.referenceFilename" = ?', 
                [filename]
            )
            if curs.fetchone()[0] > 0:
                found += 1
                logging.info(f"✓ Found: {filename}")
            else:
                not_found += 1
                logging.warning(f"✗ Not found: {filename}")
        
        logging.info(f"{found} corresponding records found.")
        logging.info(f"{not_found} corresponding records not found.")
        
        return found, not_found


class CSVExporter:
    """Handle CSV file export operations."""
    
    @staticmethod
    def export_to_csv(file_data: List[List], output_path: str) -> None:
        """Export processed file data to CSV."""
        try:
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)
                writer.writerows(file_data)
            logging.info(f"CSV file created successfully at {output_path}")
        except IOError as e:
            logging.error(f"Failed to write CSV file: {e}")
            raise


class MediaInfoExtractor:
    """Main application class that orchestrates the media info extraction process."""
    
    def __init__(self):
        self.bag_processor = BagItProcessor()
        self.json_processor = JSONSidecarProcessor()
        self.media_analyzer = MediaAnalyzer()
        self.db_manager = DatabaseManager()
        self.csv_exporter = CSVExporter()

    def collect_media_files(self, top_directory: Path, use_vendor_mode: bool) -> List[Path]:
        """Collect all media files from the specified directory."""
        files_to_examine = []
        valid_extensions = VIDEO_EXTENSIONS.union(AUDIO_EXTENSIONS)

        if use_vendor_mode:
            bags = self.bag_processor.find_bags(top_directory)
            if bags:
                for bag in bags:
                    files = self.bag_processor.get_media_files_from_bag(bag)
                    files_to_examine.extend(files)
                    if files:
                        logging.info(f"Processing {len(files)} files from {bag}")
                return files_to_examine

        # Process loose media files if no bags or not in vendor mode
        for path in top_directory.rglob('*'):
            if path.is_file() and path.suffix.lower() in valid_extensions:
                if path.name.startswith("._"):
                    logging.info(f"Skipping hidden Mac file: {path}")
                else:
                    files_to_examine.append(path)
                    logging.info(f"Adding file to processing list: {path}")

        return files_to_examine

    def process_media_files(self, files: List[Path], use_vendor_mode: bool) -> List[List]:
        """Process media files and extract metadata."""
        all_file_data = []

        for path in files:
            try:
                media_info = MediaInfo.parse(str(path))
                file_data = self.media_analyzer.extract_track_info(media_info, path)
                
                if not file_data:
                    logging.warning(f"Could not extract metadata from {path}")
                    continue

                # Handle vendor JSON sidecar data
                if use_vendor_mode:
                    json_path = path.with_suffix('.json')
                    if json_path.exists():
                        json_data = self.json_processor.read_sidecar(json_path)
                        file_data.extend([
                            json_data['collectionID'], 
                            json_data['objectType'], 
                            json_data['objectFormat']
                        ])
                    else:
                        file_data.extend([None, None, None])
                else:
                    file_data.extend([None, None, None])

                # Add bag ID
                bag_id = next((part for part in path.parts if part.startswith("MDR")), None)
                file_data.append(bag_id)
                
                all_file_data.append(file_data)
                logging.info(f"Processed file data for: {path}")
                
            except Exception as e:
                logging.error(f"Error processing file {path}: {e}")
                continue

        return all_file_data

    def prepare_data_for_output(self, all_file_data: List[List]) -> List[List]:
        """Prepare data for output by sorting and duplicating date fields."""
        # Sort by file path
        all_file_data.sort(key=lambda row: str(row[0]))

        # Duplicate dateCreated into dateCreatedText column
        for row in all_file_data:
            row.insert(6, row[5])  # Insert dateCreatedText after dateCreated

        return all_file_data

    def output_to_csv(self, file_data: List[List], output_path: str) -> None:
        """Output processed data to CSV file."""
        self.csv_exporter.export_to_csv(file_data, output_path)

    def output_to_database(self, file_data: List[List]) -> None:
        """Output processed data to database."""
        # Convert file data to record dictionaries
        all_records = []
        filenames = []

        for row in file_data:
            full_record = dict(zip(CSV_FIELD_NAMES, row[1:]))  # Skip filePath
            all_records.append(full_record)
            filenames.append(full_record['asset.referenceFilename'])

        # Filter for JDBC insertion
        insert_data = [self.db_manager.filter_for_jdbc(r) for r in all_records]

        try:
            conn = self.db_manager.connect()
            logging.info("Connection to AMIDB successful!")
            
            self.db_manager.check_corresponding_records(conn, filenames)
            self.db_manager.insert_records(conn, insert_data)
            
        except Exception as e:
            logging.error(f"Database connection or execution error: {e}")
            raise
        finally:
            if 'conn' in locals():
                conn.close()

    def run(self, args: argparse.Namespace) -> None:
        """Main execution method."""
        # Validate input directory
        top_directory = Path(args.directory)
        if not top_directory.is_dir():
            logging.error('Invalid directory path')
            return

        # Collect media files
        files_to_examine = self.collect_media_files(top_directory, args.vendor)
        
        if not files_to_examine:
            logging.error('No media files found')
            return

        # Process media files
        all_file_data = self.process_media_files(files_to_examine, args.vendor)
        
        if not all_file_data:
            logging.error('No valid media data extracted')
            return

        # Prepare data for output
        prepared_data = self.prepare_data_for_output(all_file_data)

        # Output results
        if args.output:
            self.output_to_csv(prepared_data, args.output)
        else:
            self.output_to_database(prepared_data)


def main() -> None:
    """Main entry point for the application."""
    setup_logging()
    parser = create_argument_parser()
    args = parser.parse_args()

    extractor = MediaInfoExtractor()
    extractor.run(args)


if __name__ == "__main__":
    main()