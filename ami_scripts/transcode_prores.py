#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path
import sys

# Define allowed input extensions
VALID_EXTENSIONS = {'.mkv', '.mov', '.mp4'}

def get_args():
    parser = argparse.ArgumentParser(description="Transcode MKV, MOV, and MP4 to ProRes HQ MOV")
    parser.add_argument("-i", "--input", required=True, help="Input file or directory")
    parser.add_argument("-o", "--output", required=True, help="Destination directory for ProRes files")
    return parser.parse_args()

def convert_to_prores(input_path, output_path):
    cmd = [
        "ffmpeg",
        "-hide_banner",      
        "-n",                
        "-i", str(input_path),
        "-map", "0:v",
        "-map", "0:a?",
        "-c:v", "prores_ks",
        "-profile:v", "3",
        "-c:a", "pcm_s24le",
        "-ar", "48000",
        "-stats",            
        str(output_path)
    ]
    
    print(f"\nProcessing: {input_path.name} -> {output_path.name}")
    print("-" * 60)
    
    # Run without capturing stdout/stderr so ffmpeg output flows to the terminal
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
        if input_path.suffix.lower() in VALID_EXTENSIONS:
            files_to_process.append(input_path)
        else:
            print(f"Warning: The input file '{input_path.name}' is not a supported format.")
            files_to_process.append(input_path)
            
    elif input_path.is_dir():
        print(f"Scanning '{input_path}' for compatible files...")
        for file_path in input_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in VALID_EXTENSIONS:
                if "_prores" not in file_path.stem:
                    files_to_process.append(file_path)

        if not files_to_process:
            print(f"No compatible files found in directory: {input_path}")
            return
    else:
        print(f"Error: Input path '{input_path}' does not exist.")
        sys.exit(1)

    # 3. Sort the files (Path objects sort alphabetically by default)
    files_to_process.sort()

    print(f"Found {len(files_to_process)} files to process.")

    # 4. Process the files
    for source_file in files_to_process:
        # Determine new filename based on the stem
        original_stem = source_file.stem
        
        if original_stem.endswith("_pm"):
            base_name = original_stem[:-3]
        else:
            base_name = original_stem

        new_filename = f"{base_name}_prores.mov"
        output_path = output_dir / new_filename

        try:
            convert_to_prores(source_file, output_path)
        except subprocess.CalledProcessError:
            print(f"\n[!] Failed to process: {source_file.name}")
            continue

if __name__ == "__main__":
    main()