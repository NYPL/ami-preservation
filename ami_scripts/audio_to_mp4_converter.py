#!/usr/bin/env python3

import os
import argparse
import subprocess

def convert_audio_to_mp4(file_path):
    output_file = f"{os.path.splitext(file_path)[0]}.mp4"
    command = [
        "ffmpeg",
        "-i", file_path,
        "-c:a", "aac",
        "-b:a", "320k",
        "-dither_method", "rectangular",
        "-ar", "44100",
        output_file
    ]
    subprocess.run(command, check=True)

def process_directory(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith((".wav", ".flac")):
                file_path = os.path.join(root, file)
                convert_audio_to_mp4(file_path)

def main():
    parser = argparse.ArgumentParser(description="Convert .wav or .flac files to .mp4 using ffmpeg.")
    parser.add_argument("-d", "--directory", required=True, help="Directory to process.")
    
    args = parser.parse_args()
    
    process_directory(args.directory)

if __name__ == "__main__":
    main()
