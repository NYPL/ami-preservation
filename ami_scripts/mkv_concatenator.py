#!/usr/bin/env python3
"""
Concatenate a directory of MKV video files using FFmpeg's concat demuxer.
"""
import argparse
import os
import subprocess
import sys
import tempfile

def parse_args():
    parser = argparse.ArgumentParser(
        description='Concatenate MKV video files using ffmpeg concat demuxer'
    )
    parser.add_argument(
        '-d', '--directory',
        required=True,
        help='Directory containing source MKV files'
    )
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Output file path (including filename, should end with .mkv)'
    )
    return parser.parse_args()

def validate_paths(input_dir: str, output_path: str) -> tuple[str, str]:
    # Check source directory
    if not os.path.isdir(input_dir):
        sys.exit(f"Error: Directory '{input_dir}' does not exist or is not a directory.")
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path) or '.'
    if not os.path.isdir(output_dir):
        sys.exit(f"Error: Output directory '{output_dir}' does not exist.")
    return os.path.abspath(input_dir), os.path.abspath(output_path)

def build_file_list(input_dir: str) -> list[str]:
    # Collect and sort only MKV files in the directory
    files = sorted(
        f for f in os.listdir(input_dir)
        if f.lower().endswith('.mkv') and os.path.isfile(os.path.join(input_dir, f))
    )
    if not files:
        sys.exit(f"Error: No .mkv files found in directory '{input_dir}'.")
    return files

def write_ffmpeg_list(files: list[str], input_dir: str) -> str:
    # Write a temporary list file for ffmpeg concat
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tf:
        for filename in files:
            path = os.path.join(input_dir, filename)
            tf.write(f"file '{path}'\n")
        return tf.name

def concatenate(input_dir: str, output_path: str) -> None:
    files = build_file_list(input_dir)
    list_file = write_ffmpeg_list(files, input_dir)
    cmd = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',        # allows absolute paths in list file
        '-i', list_file,
        '-c', 'copy',
        output_path
    ]
    print(f"Running command: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully created concatenated file: {output_path}")
    finally:
        os.remove(list_file)

def main():
    args = parse_args()
    input_dir, output_path = validate_paths(args.directory, args.output)
    concatenate(input_dir, output_path)

if __name__ == '__main__':
    main()