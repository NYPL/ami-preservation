#!/usr/bin/env python3

import argparse
import os
import subprocess
from pathlib import Path

def get_args():
    parser = argparse.ArgumentParser(description="Transcode MKV to ProRes HQ MOV")
    parser.add_argument("-i", "--input", required=True, help="Input directory to search recursively for MKV files")
    parser.add_argument("-d", "--destination", required=True, help="Destination directory for ProRes files")
    return parser.parse_args()

def convert_to_prores(input_path, output_path):
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-map", "0",
        "-map", "0:a?",
        "-c:v", "prores_ks",
        "-profile:v", "3",  # ProRes HQ
        "-c:a", "pcm_s24le",  # 24-bit PCM
        str(output_path)
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

def main():
    args = get_args()
    input_dir = Path(args.input)
    destination_dir = Path(args.destination)
    destination_dir.mkdir(parents=True, exist_ok=True)

    for mkv_file in input_dir.rglob("*.mkv"):
        if "_pm.mkv" in mkv_file.name:
            new_name = mkv_file.name.replace("_pm.mkv", "_prores.mov")
        else:
            new_name = mkv_file.stem + "_prores.mov"

        output_path = destination_dir / new_name

        try:
            convert_to_prores(mkv_file, output_path)
        except subprocess.CalledProcessError as e:
            print(f"Error processing {mkv_file}: {e}")

if __name__ == "__main__":
    main()
