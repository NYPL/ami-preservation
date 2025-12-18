#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path
import sys

def get_args():
    parser = argparse.ArgumentParser(description="Transcode MKV to ProRes HQ MOV")
    parser.add_argument("-i", "--input", required=True, help="Input file or directory")
    parser.add_argument("-o", "--output", required=True, help="Destination directory for ProRes files")
    return parser.parse_args()

def convert_to_prores(input_path, output_path):
    cmd = [
        "ffmpeg",
        "-n",               # Do not overwrite output file if it exists (optional safety)
        "-i", str(input_path),
        "-map", "0:v",
        "-map", "0:a?",
        "-c:v", "prores_ks",
        "-profile:v", "3",  # ProRes HQ
        "-c:a", "pcm_s24le", # 24-bit PCM
        "-ar", "48000"
        str(output_path)
    ]
    
    print(f"Processing: {input_path.name} -> {output_path.name}")
    # Using subprocess.run to execute ffmpeg
    subprocess.run(cmd, check=True)

def main():
    args = get_args()
    input_path = Path(args.input)
    output_dir = Path(args.output)

    # 1. Create the output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Determine the list of files to process
    files_to_process = []

    if input_path.is_file():
        # If input is a single file, just add it to the list
        if input_path.suffix.lower() == '.mkv':
            files_to_process.append(input_path)
        else:
            print(f"Warning: The input file '{input_path.name}' does not appear to be an .mkv file.")
            files_to_process.append(input_path)
            
    elif input_path.is_dir():
        # If input is a directory, search recursively for .mkv
        files_to_process = list(input_path.rglob("*.mkv"))
        if not files_to_process:
            print(f"No MKV files found in directory: {input_path}")
            return
    else:
        print(f"Error: Input path '{input_path}' does not exist.")
        sys.exit(1)

    # 3. Process the files
    for mkv_file in files_to_process:
        # Determine new filename
        if "_pm.mkv" in mkv_file.name:
            new_name = mkv_file.name.replace("_pm.mkv", "_prores.mov")
        else:
            new_name = mkv_file.stem + "_prores.mov"

        output_path = output_dir / new_name

        try:
            convert_to_prores(mkv_file, output_path)
        except subprocess.CalledProcessError as e:
            print(f"Error processing {mkv_file.name}: {e}")

if __name__ == "__main__":
    main()