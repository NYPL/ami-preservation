#!/usr/bin/env python3

import os
import argparse
import subprocess
import shutil
import csv
import logging
import re
from pathlib import Path
from pymediainfo import MediaInfo
import multiprocessing
from functools import partial

LOGGER = logging.getLogger(__name__)

video_extensions = {'.mkv', '.mov', '.mp4', '.dv', '.iso'}
audio_extensions = {'.wav', '.flac'}

def convert_to_mp4(input_file, input_directory):
    output_file_name = f"{input_file.stem.replace('_mz', '')}_sc.mp4"
    output_file = input_directory / output_file_name
    command = [
        "ffmpeg",
        "-i", str(input_file),
        "-map", "0:v", "-map", "0:a?",
        "-c:v", "libx264",
        "-movflags", "faststart",
        "-pix_fmt", "yuv420p",
        "-crf", "21",
        "-c:a", "aac", "-b:a", "320000", "-ar", "48000", str(output_file)
    ]
    LOGGER.info("Converting %s to MP4 as %s", input_file, output_file)
    subprocess.run(command)

def move_dpx_files_to_to_delete(pm_folder, film_folder):
    """
    Moves all DPX files from pm_folder into a TO_DELETE folder.
    The TO_DELETE folder is placed in the parent directory of film_folder,
    with a subdirectory named after film_folder.
    """
    to_delete_root = film_folder.parent / "TO_DELETE"
    to_delete_folder = to_delete_root / film_folder.name
    to_delete_folder.mkdir(parents=True, exist_ok=True)
    
    dpx_files = list(pm_folder.glob('*.dpx'))
    if dpx_files:
        LOGGER.info("Moving %d DPX files from %s to %s", len(dpx_files), pm_folder, to_delete_folder)
        for file in dpx_files:
            try:
                shutil.move(str(file), str(to_delete_folder / file.name))
            except Exception as e:
                LOGGER.error("Error moving %s: %s", file, e)
    else:
        LOGGER.info("No DPX files found in %s to move.", pm_folder)

def move_and_clean(film_folder, pm_folder, output_name):
    """
    Moves the output file (rawcooked result) into pm_folder, then
    moves all DPX files to the TO_DELETE folder and deletes any other leftover items.
    """
    dest = pm_folder / output_name.name
    LOGGER.info("Moving file %s to %s", output_name, dest)
    shutil.move(str(output_name), str(dest))
    
    # Instead of deleting DPX files, move them into a TO_DELETE folder.
    move_dpx_files_to_to_delete(pm_folder, film_folder)
    
    # Remove any remaining files or directories in pm_folder except the preserved output.
    LOGGER.info("Removing remaining items in %s except %s", pm_folder, dest)
    for item in pm_folder.glob('*'):
        if item != dest:
            try:
                if item.is_file():
                    LOGGER.info("Deleting file: %s", item)
                    item.unlink()
                elif item.is_dir():
                    LOGGER.info("Deleting directory: %s", item)
                    shutil.rmtree(item)
            except Exception as e:
                LOGGER.error("Error deleting %s: %s", item, e)
    LOGGER.info("Cleanup completed for %s", pm_folder)

def copy_to_editmasters(pm_folder, flac_file):
    em_folder = pm_folder.parent / 'EditMasters'
    em_folder.mkdir(exist_ok=True)
    
    em_file_name = flac_file.stem.replace('_pm', '_em') + '.flac'
    em_file = em_folder / em_file_name
    LOGGER.info("Copying %s to EditMasters folder as %s", flac_file, em_file)
    shutil.copy(str(flac_file), str(em_file))

def remove_hidden_files(directory):
    for item in directory.rglob('.*'):
        if item.is_file():
            LOGGER.info("Removing hidden file: %s", item)
            item.unlink()

def process_directory(root_dir):
    for film_folder in sorted(Path(root_dir).glob('*')):
        if not film_folder.is_dir():
            continue

        # Remove hidden files
        remove_hidden_files(film_folder)
        pm_folder = film_folder / 'PreservationMasters'
        mz_folder = film_folder / 'Mezzanines'

        if not pm_folder.exists():
            LOGGER.error("Error: Missing required folder(s) in %s", film_folder)
            continue

        # Detect files in PreservationMasters
        wav_file = next(pm_folder.glob('*.wav'), None)
        dpx_files = list(pm_folder.glob('*.dpx'))
        mkv_file = next(pm_folder.glob('*.mkv'), None)

        # 1) DPX sequence processing (unchanged)
        if dpx_files:
            sc_folder = film_folder / 'ServiceCopies'
            sc_folder.mkdir(exist_ok=True)

            mz_file = next(iter(sorted(mz_folder.glob('*.mov'))), None)
            first_dpx = sorted(dpx_files)[0]
            # derive stem by stripping the trailing frame index (_0000000)
            output_stem = first_dpx.stem[:-8]
            output_mkv = film_folder / f"{output_stem}.mkv"

            LOGGER.info("Processing DPX folder %s...", film_folder)
            rawcooked_cmd = [
                'rawcooked', '--no-accept-gaps', '--no-check-padding',
                str(pm_folder), '--output-name', str(output_mkv)
            ]
            result = subprocess.run(rawcooked_cmd)

            if result.returncode == 0:
                move_and_clean(film_folder, pm_folder, output_mkv)
                if mz_file:
                    convert_to_mp4(mz_file, sc_folder)
                else:
                    LOGGER.error("No Mezzanine file found in %s", mz_folder)
            else:
                LOGGER.error("rawcooked failed for %s", film_folder)

        # 2) Audio WAV processing (unchanged)
        elif wav_file:
            output_flac = wav_file.with_suffix('.flac')
            flac_cmd = [
                'flac', str(wav_file), '--best', '--preserve-modtime', '--verify', '-o', str(output_flac)
            ]
            LOGGER.info("Converting WAV %s to FLAC %s", wav_file, output_flac)
            if subprocess.call(flac_cmd) == 0:
                wav_file.unlink()
                copy_to_editmasters(pm_folder, output_flac)
            else:
                LOGGER.error("FLAC conversion failed for %s", wav_file)

        # 3) Direct-scanned MKV processing (new scenario)
        elif mkv_file:
            # Rename to strip trailing frame-index
            base = mkv_file.stem.rsplit('_', 1)[0]
            new_mkv = pm_folder / f"{base}.mkv"
            LOGGER.info("Renaming %s to %s", mkv_file, new_mkv)
            mkv_file.rename(new_mkv)

            # Transcode the mezzanine MOV to MP4
            sc_folder = film_folder / 'ServiceCopies'
            sc_folder.mkdir(exist_ok=True)
            mz_file = next(iter(sorted(mz_folder.glob('*.mov'))), None)
            if mz_file:
                convert_to_mp4(mz_file, sc_folder)
            else:
                LOGGER.error("No Mezzanine file found in %s", mz_folder)

        # 4) Nothing to do
        else:
            LOGGER.error("No DPX, WAV, or MKV files found in %s", pm_folder)

def collect_media_files(directory):
    valid_extensions = video_extensions.union(audio_extensions)
    return [path for path in directory.rglob('*') if path.is_file() and path.suffix.lower() in valid_extensions]

def has_mezzanines(file_path):
    for parent in file_path.parents:
        mezzanines_dir = parent / "Mezzanines"
        if mezzanines_dir.is_dir():
            return True
    return False

def extract_track_info(media_info, path, project_code_pattern, valid_extensions):
    for track in media_info.tracks:
        if track.track_type == "General":
            file_data = [
                path,
                '.'.join([path.stem, path.suffix[1:]]),
                path.stem,
                path.suffix[1:],
                track.file_size,
                track.file_last_modification_date.split()[1],
                track.format,
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

            match = project_code_pattern.search(str(path))
            if match:
                projectcode = match.group(1)
                file_data.append(projectcode)
            else:
                file_data.append(None)

            return file_data

    return None

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    parser = argparse.ArgumentParser(description='Process media files from motion picture film digitization.')
    parser.add_argument('-d', '--directory', dest='input_dir', required=True, help='Path to the root directory containing the media files.')
    parser.add_argument('-o', '--output', dest='output_csv', required=False, help='Path to save the CSV with MediaInfo.')
    args = parser.parse_args()

    root_path = Path(args.input_dir)
    if root_path.exists() and root_path.is_dir():
        process_directory(root_path)
        
        # If the output CSV argument is provided, run the MediaInfo extraction
        if args.output_csv:
            files_to_examine = collect_media_files(root_path)
            all_file_data = []

            project_code_pattern = re.compile(r'(\d\d\d\d\_\d+)')
            for path in files_to_examine:
                if "RECYCLE.BIN" not in path.parts:
                    media_info = MediaInfo.parse(str(path))
                    file_data = extract_track_info(media_info, path, project_code_pattern, video_extensions.union(audio_extensions))
                    if file_data:
                        LOGGER.info("Extracted data for %s: %s", path, file_data)
                        all_file_data.append(file_data)

            with open(args.output_csv, 'w') as f:
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
                    'primaryID',
                    'projectID'
                ])
                md_csv.writerows(all_file_data)
    else:
        LOGGER.error("Error: %s does not exist or is not a directory.", root_path)
