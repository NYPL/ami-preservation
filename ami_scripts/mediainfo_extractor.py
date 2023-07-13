#!/usr/bin/env python3

#!/usr/bin/env python3

import argparse
import csv
import logging
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from pprint import pprint
from pymediainfo import MediaInfo

LOGGER = logging.getLogger(__name__)

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

    return parser

def process_directory(directory):
    valid_extensions = video_extensions.union(audio_extensions)
    media_files = []
    for path in directory.rglob('*'):
        if path.is_file() and path.suffix.lower() in valid_extensions:
            if path.name.startswith("._"):
                print(f"Skipping hidden Mac file: {path}")
            else:
                media_files.append(path)
    return media_files

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
        file_system_type = root.find(".//{http://kb.nl/ns/isolyzer/v1/}fileSystem").attrib['TYPE']
        return file_system_type
    except subprocess.CalledProcessError as e:
        print(f"Isolyzer failed with error: {e}")
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
    if not is_tool('isolyzer'):
        print('Error: Isolyzer is not installed or not found in PATH. Please install (pip3 install isolyzer) before running this script.')
        return
    parser = make_parser()
    args = parser.parse_args()

    files_to_examine = []

    if args.directory:
        directory = Path(args.directory)
        if directory.is_dir():
            files_to_examine.extend(process_directory(directory))

    if args.file:
        file = Path(args.file)
        if file.is_file() and file.suffix.lower() in video_extensions.union(audio_extensions):
            files_to_examine.append(file)

    if not files_to_examine:
        print('Error: Please enter a directory or single file')
        return

    all_file_data = []

    for path in files_to_examine:
        if "RECYCLE.BIN" in path.parts:
            print('RECYCLING BIN WITH MEDIA FILES!!!')
        else:
            media_info = MediaInfo.parse(str(path))
            file_data = extract_track_info(media_info, path, video_extensions.union(audio_extensions))
            if file_data:
                print(file_data)
                all_file_data.append(file_data)

    with open(args.output, 'w') as f:
        md_csv = csv.writer(f)
        md_csv.writerow([
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
            'primaryID'])
        md_csv.writerows(all_file_data)

if __name__ == "__main__":
    main()
