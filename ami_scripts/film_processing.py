#!/usr/bin/env python3

import os
import argparse
import subprocess
from pathlib import Path
import shutil

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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process media files from motion picture film digitization.')
    parser.add_argument('-d', '--directory', dest='input_dir', required=True, help='Path to the root directory containing the media files.')
    args = parser.parse_args()

    root_path = Path(args.input_dir)
    if root_path.exists() and root_path.is_dir():
        process_directory(root_path)
    else:
        print(f"Error: {root_path} does not exist or is not a directory.")

       
