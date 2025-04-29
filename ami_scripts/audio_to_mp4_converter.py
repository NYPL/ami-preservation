#!/usr/bin/env python3

import os
import argparse
import subprocess

def convert_audio(file_path, output_format):
    if output_format == "mp3":
        output_file = f"{os.path.splitext(file_path)[0]}.mp3"
        command = [
            "ffmpeg",
            "-i", file_path,
            "-write_id3v1", "1",
            "-id3v2_version", "3",
            "-dither_method", "triangular",
            "-ar", "48000",
            "-qscale:a", "1",
            output_file
        ]
    else:
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

def process_directory(directory, output_format):
    for root, _, files in os.walk(directory):
        for file in sorted(files):
            if file.endswith((".wav", ".flac", ".WMA")):
                file_path = os.path.join(root, file)
                convert_audio(file_path, output_format)

def main():
    parser = argparse.ArgumentParser(description="Convert .wav or .flac files to .mp4 or .mp3 using ffmpeg.")
    parser.add_argument("-d", "--directory", required=True, help="Directory to process.")
    parser.add_argument("-f", "--format", choices=["mp4", "mp3"], default="mp4", help="Output format: mp4 (default) or mp3.")
    
    args = parser.parse_args()
    
    process_directory(args.directory, args.format)

if __name__ == "__main__":
    main()
