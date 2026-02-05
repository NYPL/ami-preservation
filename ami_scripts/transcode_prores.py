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
    # Added the HD flag
    parser.add_argument("--hd", action="store_true", help="Upscale SD to 1080p HD with pillarboxing and deinterlacing")
    return parser.parse_args()

def convert_to_prores(input_path, output_path, use_hd_recipe):
    cmd = [
        "ffmpeg",
        "-hide_banner",      
        "-n",                
        "-i", str(input_path),
        "-map", "0:v",
        "-map", "0:a?",
    ]

    # Handle the HD Upscale + Deinterlace Logic
    if use_hd_recipe:
        # idet detects field order, bwdif deinterlaces
        # colormatrix fixes the SD -> HD color shift
        # scale + pad creates the 4:3 inside 16:9 frame
        video_filters = (
            "idet,bwdif=1,"
            "colormatrix=bt601:bt709,"
            "scale=1440:1080:flags=lanczos,"
            "pad=1920:1080:240:0"
        )
        cmd.extend(["-filter:v", video_filters])
    
    # Standard ProRes and Audio Settings
    cmd.extend([
        "-c:v", "prores_ks",
        "-profile:v", "3",
        "-c:a", "pcm_s24le",
        "-ar", "48000",
        "-stats",            
        str(output_path)
    ])
    
    print(f"\nProcessing: {input_path.name} -> {output_path.name}")
    if use_hd_recipe:
        print("Mode: SD to HD Pillarbox (Deinterlaced)")
    print("-" * 60)
    
    subprocess.run(cmd, check=True)

def main():
    args = get_args()
    input_path = Path(args.input)
    output_dir = Path(args.output)

    output_dir.mkdir(parents=True, exist_ok=True)

    files_to_process = []

    if input_path.is_file():
        if input_path.suffix.lower() in VALID_EXTENSIONS:
            files_to_process.append(input_path)
        else:
            print(f"Warning: The input file '{input_path.name}' is not supported.")
            
    elif input_path.is_dir():
        print(f"Scanning '{input_path}' for compatible files...")
        for file_path in input_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in VALID_EXTENSIONS:
                if "_prores" not in file_path.stem:
                    files_to_process.append(file_path)

    if not files_to_process:
        print(f"No compatible files found.")
        return

    files_to_process.sort()
    print(f"Found {len(files_to_process)} files to process.")

    for source_file in files_to_process:
        original_stem = source_file.stem
        base_name = original_stem[:-3] if original_stem.endswith("_pm") else original_stem

        # Differentiate the filename if HD is applied
        suffix = "_HD_prores.mov" if args.hd else "_prores.mov"
        new_filename = f"{base_name}{suffix}"
        output_path = output_dir / new_filename

        try:
            convert_to_prores(source_file, output_path, args.hd)
        except subprocess.CalledProcessError:
            print(f"\n[!] Failed to process: {source_file.name}")
            continue

if __name__ == "__main__":
    main()