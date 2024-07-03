#!/usr/bin/env python3

import argparse
import os
import subprocess

def process_video(input_file, output_dir):
    # Extract the base name and construct the output file path
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    if output_dir:
        output_file = os.path.join(output_dir, f"{base_name}_sc.mp4")
    else:
        output_file = os.path.join(os.path.dirname(input_file), f"{base_name}_sc.mp4")

    # Build the FFmpeg command
    command = [
        'ffmpeg', '-i', input_file, '-map', '0:a', '-map', '0:v',
        '-c:v', 'libx264', '-movflags', 'faststart', '-pix_fmt', 'yuv420p',
        '-b:v', '3500000', '-bufsize', '1750000', '-maxrate', '3500000',
        '-vf', 'yadif,setdar=16/9', '-c:a', 'aac', '-b:a', '320000',
        '-ar', '48000', output_file
    ]

    # Execute the FFmpeg command
    subprocess.run(command, check=True)
    print(f"Processed {input_file} to {output_file}")

def main():
    # Setup argument parser
    parser = argparse.ArgumentParser(description="Process MKV videos to anamorphic service copies.")
    parser.add_argument('-f', '--file', type=str, help="Single MKV file to process.")
    parser.add_argument('-d', '--directory', type=str, help="Directory containing MKV files to process.")
    parser.add_argument('-o', '--output', type=str, help="Optional output directory for the processed files.")

    args = parser.parse_args()

    # Check the input options
    if args.file:
        process_video(args.file, args.output)
    elif args.directory:
        # Process each MKV file in the directory
        for filename in os.listdir(args.directory):
            if filename.endswith('.mkv'):  # Only accept MKV files
                file_path = os.path.join(args.directory, filename)
                process_video(file_path, args.output)
    else:
        print("No input file or directory specified.")
        parser.print_help()

if __name__ == '__main__':
    main()
