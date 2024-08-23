#!/usr/bin/env python3

import argparse
import os
import subprocess

def process_video(input_file, top_lines, bottom_lines, preview, save):
    file_dir, file_name = os.path.split(input_file)
    file_base, _ = os.path.splitext(file_name)
    output_file = os.path.join(file_dir, f"{file_base}_processed.mp4")
    
    vf_filter = []

    if top_lines > 0:
        # Cover the top part of the video
        vf_filter.append(f"drawbox=y=0:h={top_lines}:color=black:t=fill")
    
    if bottom_lines > 0:
        # Cover the bottom part of the video
        vf_filter.append(f"drawbox=y=ih-{bottom_lines}:h={bottom_lines}:color=black:t=fill")
    
    # Join the filters with a comma if both are used
    vf_filter_str = ",".join(vf_filter)
    
    if preview:
        command = ["ffplay", "-i", input_file]
        if vf_filter_str:
            command.extend(["-vf", vf_filter_str])
    else:
        command = [
            "ffmpeg", "-i", input_file,
            "-map", "0:a", "-map", "0:v",
            "-c:v", "libx264", "-movflags", "faststart",
            "-pix_fmt", "yuv420p", "-b:v", "3500000",
            "-bufsize", "1750000", "-maxrate", "3500000",
            "-vf", f"{vf_filter_str},yadif" if vf_filter_str else "yadif",
            "-c:a", "aac", "-strict", "-2",
            "-b:a", "320000", "-ar", "48000",
            output_file
        ]
    
    subprocess.run(command)

def main():
    parser = argparse.ArgumentParser(description="Cover top or bottom lines of video files with black.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-d", "--directory", help="Directory of video files.")
    group.add_argument("-f", "--file", help="Path to a single video file.")
    parser.add_argument("-t", "--top", type=int, default=0, help="Number of lines to cover at the top.")
    parser.add_argument("-b", "--bottom", type=int, default=0, help="Number of lines to cover at the bottom.")
    parser.add_argument("-p", "--preview", action="store_true", help="Preview the result using FFplay.")
    parser.add_argument("-s", "--save", action="store_true", help="Save the processed video.")

    args = parser.parse_args()

    if not args.preview and not args.save:
        print("You must specify either --preview (-p) or --save (-s).")
        return

    if args.directory:
        video_files = [os.path.join(args.directory, f) for f in os.listdir(args.directory) if f.endswith(('.mp4', '.mov', '.avi', '.mkv'))]
    elif args.file:
        video_files = [args.file]

    for video_file in video_files:
        process_video(video_file, args.top, args.bottom, args.preview, args.save)

if __name__ == "__main__":
    main()
