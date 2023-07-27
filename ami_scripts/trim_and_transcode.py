#!/usr/bin/env python3
import argparse
import subprocess
import shlex
import os

def transcode_file(input_file, output_dir, start_time, end_time):
    # Construct output filename
    base_name = os.path.basename(input_file)
    name, ext = os.path.splitext(base_name)
    output_file = os.path.join(output_dir, f"{name}_trim.mp4")

    # ffmpeg command for transcoding and trimming
    command = f"""ffmpeg -ss {start_time} -to {end_time} -i {input_file} -map 0:v -map 0:a -c:v libx264 -movflags faststart -pix_fmt yuv420p -b:v 3500000 -bufsize 1750000 -maxrate 3500000 -vf "yadif,fade=t=in:st=0:d=2,fade=t=out:st={end_time - start_time - 2}:d=2" -c:a aac -b:a 320000 -ar 48000 -af "afade=t=in:st=0:d=2,afade=t=out:st={end_time - start_time - 2}:d=2" {output_file}"""
    
    subprocess.call(shlex.split(command))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Trim and transcode media file.')
    parser.add_argument('-f', '--file', type=str, required=True, help='Input media file')
    parser.add_argument('-o', '--output', type=str, required=True, help='Output directory')
    parser.add_argument('-t', '--timestamp', type=str, required=True, nargs=2, help='Start and end timestamps in the format HH:MM:SS')

    args = parser.parse_args()
    
    input_file = args.file
    output_dir = args.output

    start_time, end_time = [sum(int(x) * 60 ** i for i,x in enumerate(reversed(t.split(":")))) for t in args.timestamp]

    transcode_file(input_file, output_dir, start_time, end_time)
