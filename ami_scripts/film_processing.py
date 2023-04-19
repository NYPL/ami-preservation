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
        "-b:v", "8000000", "-bufsize", "5000000", "-maxrate", "8000000",
        "-vf", "yadif",
        "-c:a", "aac", "-b:a", "320000", "-ar", "48000", str(output_file)
    ]
    subprocess.run(command)


def move_and_clean(pm_folder, output_name):
    # Move the output file to the PreservationMasters folder
    shutil.move(str(output_name), str(pm_folder / output_name.name))

    # Delete the contents of the PreservationMasters folder, except the output file
    for item in pm_folder.glob('*'):
        if item != pm_folder / output_name.name:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)


def copy_to_editmasters(pm_folder, flac_file):
    em_folder = pm_folder.parent / 'EditMasters'
    em_folder.mkdir(exist_ok=True)
    
    em_file_name = flac_file.stem.replace('_pm', '_em') + '.flac'
    em_file = em_folder / em_file_name
    shutil.copy(str(flac_file), str(em_file))


def process_directory(root_dir):
    for folder in sorted(root_dir.glob('*')):
        if folder.is_dir():
            pm_folder = folder / 'PreservationMasters'
            mz_folder = folder / 'Mezzanines'

            if pm_folder.exists():
                # Check for WAV files in the PreservationMasters folder
                wav_file = next(iter(pm_folder.glob('*.wav')), None)

                # Check for DPX files in the PreservationMasters folder
                dpx_files = list(pm_folder.glob('*.dpx'))

                if dpx_files:  # If DPX files exist (including cases with WAV file)
                    sc_folder = folder / 'ServiceCopies'
                    sc_folder.mkdir(exist_ok=True)

                    mz_file = next(iter(sorted(mz_folder.glob('*.mov'))), None)
                    first_dpx_file = next(iter(sorted(dpx_files)), None)

                    if first_dpx_file is not None:
                        output_stem = first_dpx_file.stem[:-8]
                        output_name = folder / f"{output_stem}.mkv"

                    if mz_file:
                        print(f"Processing {folder}...")
                        rawcooked_cmd = ['rawcooked', '--no-accept-gaps', '--no-check-padding',
                                          pm_folder, '--output-name', output_name]
                        result = subprocess.run(rawcooked_cmd)

                        if result.returncode == 0:
                            move_and_clean(pm_folder, output_name)
                            convert_to_mp4(mz_file, sc_folder)
                        else:
                            print(f"Error: rawcooked command failed for {folder}")

                    else:
                        print(f"Error: No Mezzanine file found in {mz_folder}")

                if wav_file:  # If a WAV file is found, run the flac command (covers both cases with and without DPX files)
                    output_file = wav_file.with_suffix('.flac')
                    flac_command = [
                        'flac', str(wav_file),
                        '--best',
                        '--preserve-modtime',
                        '--verify',
                        '-o', str(output_file)
                    ]
                    return_code = subprocess.call(flac_command)

                    if return_code == 0:  # If the command ran successfully, delete the WAV file
                        wav_file.unlink()
                        copy_to_editmasters(pm_folder, output_file)

                elif not dpx_files:
                    print(f"Error: No DPX files or WAV file found in {pm_folder}")

            else:
                print(f"Error: Missing required folder(s) in {folder}")


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
                        print(file_data)
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
        print(f"Error: {root_path} does not exist or is not a directory.")
