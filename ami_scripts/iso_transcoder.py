#!/usr/bin/env python3

import argparse
from pathlib import Path
import subprocess
import logging
import tempfile
import sys
import os

# Check for colorama installation
try:
    from colorama import Fore, Style
except ImportError:
    print("colorama is not installed. Please install it by running: python3 -m pip install colorama")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def verify_makemkvcon_installation():
    try:
        result = subprocess.run(["makemkvcon", "-r", "info", "disc:9999"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return  # Expected failure, but makemkvcon is installed.
    except FileNotFoundError:
        print("makemkvcon is not found in your system's path. Please make sure MakeMKV is installed.")
        sys.exit(1)


def process_iso_with_makemkv(iso_path, output_directory):
    logging.info(f"Processing ISO {iso_path} with MakeMKV")
    output_path = Path(tempfile.mkdtemp())  # Temporary directory for MKVs
    
    makemkv_command = ["makemkvcon", "mkv", f"iso:{iso_path}", "all", str(output_path)]
    try:
        subprocess.run(makemkv_command, check=True)
        logging.info(f"MKV files created from {iso_path} in {output_path}")
        return output_path
    except subprocess.CalledProcessError:
        logging.error(f"MakeMKV processing failed for {iso_path}")
        return None
    

def build_ffmpeg_command(input_file, output_file):
    ffmpeg_command = [
        "ffmpeg", "-i", str(input_file),
        "-c:v", "libx264",
        "-movflags", "faststart",
        "-pix_fmt", "yuv420p",
        "-b:v", "3500000",
        "-bufsize", "1750000",
        "-maxrate", "3500000",
        "-vf", "yadif",
        "-c:a", "aac",
        "-b:a", "320000",
        "-ar", "48000",
        str(output_file)
    ]
    return ffmpeg_command

def concatenate_mkvs(mkv_files):
    try:
        with tempfile.NamedTemporaryFile(suffix=".mkv", delete=False) as tmp_mkv_file:
            mkvmerge_command = ["mkvmerge", "-o", tmp_mkv_file.name]
            for mkv_file in mkv_files[:-1]:
                mkvmerge_command.extend([str(mkv_file), "+"])
            mkvmerge_command.append(str(mkv_files[-1]))
            subprocess.run(mkvmerge_command, check=True)
            return tmp_mkv_file.name
    except subprocess.CalledProcessError:
        logging.error("MKVMerge failed, could not concatenate MKVs.")
        return None

def transcode_mkv_files(mkv_directory, iso_basename, output_directory, force_concat):
    mkv_files = sorted(mkv_directory.glob("*.mkv"))
    if not mkv_files:
        logging.error(f"No MKV files found in {mkv_directory}")
        return
    
    if force_concat:
        logging.info("Concatenating MKV files using mkvmerge...")
        concatenated_mkv = concatenate_mkvs(mkv_files)
        if concatenated_mkv:
            output_file = output_directory / f"{iso_basename}_sc.mp4"
            logging.info(f"Transcoding concatenated MKV to {output_file}")
            ffmpeg_command = build_ffmpeg_command(concatenated_mkv, output_file)
            try:
                subprocess.run(ffmpeg_command, check=True)
            except subprocess.CalledProcessError:
                logging.error(f"Transcoding failed for concatenated MKV of {iso_basename}")
            finally:
                Path(concatenated_mkv).unlink()  # Clean up concatenated temp MKV file
        else:
            logging.error(f"Concatenation failed for {iso_basename}, skipping transcoding.")
    else:
        for idx, mkv_file in enumerate(mkv_files, start=1):
            output_file = output_directory / f"{iso_basename}f01r{str(idx).zfill(2)}_sc.mp4" if len(mkv_files) > 1 else output_directory / f"{iso_basename}_sc.mp4"
            logging.info(f"Transcoding {mkv_file} to {output_file}")
            
            ffmpeg_command = build_ffmpeg_command(mkv_file, output_file)
            try:
                subprocess.run(ffmpeg_command, check=True)
            except subprocess.CalledProcessError:
                logging.error(f"Transcoding failed for {mkv_file}")

def verify_transcoding(iso_paths, output_directory):
    total_isos = len(iso_paths)
    successful_isos = []
    failed_isos = []
    print(f"\n{Style.BRIGHT}File Creation Summary:{Style.RESET_ALL}")

    for iso_path in iso_paths:
        iso_basename = iso_path.stem.replace("_pm", "")
        expected_output_files = [file for file in os.listdir(output_directory) if file.startswith(iso_basename) and file.endswith('.mp4')]

        if not expected_output_files:
            logging.error(f"No MP4 files were created for ISO: {iso_path}")
            failed_isos.append(iso_path)
        else:
            logging.info(f"{len(expected_output_files)} MP4 files were created for ISO: {iso_path}")
            successful_isos.append(iso_path)

    # Print summary with color
    print(f"\n{Style.BRIGHT}Processing Summary:{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Total ISOs processed: {total_isos}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Successfully processed: {len(successful_isos)}{Style.RESET_ALL}")
    print(f"{Fore.RED}Failed to process: {len(failed_isos)}{Style.RESET_ALL}")

    if failed_isos:
        print(f"\n{Fore.RED}List of failed ISOs:{Style.RESET_ALL}")
        for iso in failed_isos:
            print(f" - {iso}")

def main():
    parser = argparse.ArgumentParser(description='Transcode MKV files created from ISO images to H.264 MP4s.')
    parser.add_argument('-i', '--input', dest='i', required=True, help='Path to the input directory with ISO files')
    parser.add_argument('-o', '--output', dest='o', required=True, help='Output directory for MP4 files')
    parser.add_argument('-f', '--force', action='store_true', help='Force concatenation of MKV files before transcoding')
    args = parser.parse_args()

    verify_makemkvcon_installation()

    input_directory = Path(args.i)
    output_directory = Path(args.o)
    output_directory.mkdir(parents=True, exist_ok=True)

    iso_files = list(sorted(input_directory.glob('*.iso')))
    processed_iso_paths = []

    for iso_file in iso_files:
        iso_basename = iso_file.stem.replace("_pm", "")
        mkv_output_dir = process_iso_with_makemkv(iso_file, output_directory)

        if mkv_output_dir:
            transcode_mkv_files(mkv_output_dir, iso_basename, output_directory, args.force)
            processed_iso_paths.append(iso_file)
            # Clean up temporary MKV directory
            for mkv_file in mkv_output_dir.glob("*.mkv"):
                mkv_file.unlink()
            mkv_output_dir.rmdir()
        else:
            logging.error(f"Skipping transcoding for {iso_file} due to MakeMKV processing failure.")

    # Verify transcoding results and print a summary
    verify_transcoding(processed_iso_paths, output_directory)

if __name__ == "__main__":
    main()
