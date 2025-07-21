#!/usr/bin/env python3
import argparse
import subprocess
import os

def transcode_file(input_file, output_dir, start_time, end_time, hd, prores, mp4):
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Calculate clip duration and fade-out start
    duration = end_time - start_time
    fade_out_start = max(duration - 2, 0)

    # Build base name and output path
    base_name = os.path.basename(input_file)
    name, _ = os.path.splitext(base_name)
    
    if prores:
        ext = ".mov"
    else:  # mp4
        ext = ".mp4"
    output_file = os.path.join(output_dir, f"{name}_trim{ext}")

    # Common fade filters
    fade_v_in  = "fade=t=in:st=0:d=2"
    fade_v_out = f"fade=t=out:st={fade_out_start}:d=2"
    fade_a     = f"afade=t=in:st=0:d=2,afade=t=out:st={fade_out_start}:d=2"

    if prores:
        # ProRes branch: profile 3, PCM audio, optional HD up-res & pillarbox
        vf_chain = []
        if hd:
            vf_chain += [
                "colormatrix=bt601:bt709",
                "scale=1440:1080:flags=lanczos",
                "pad=1920:1080:240:0"
            ]
        vf_chain += [fade_v_in, fade_v_out]
        vf = ",".join(vf_chain)

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time), "-to", str(end_time),
            "-i", input_file,
            "-map", "0:v", "-map", "0:a",
            "-c:v", "prores", "-profile:v", "3",
            "-vf", vf,
            "-c:a", "pcm_s24le",
            "-af", fade_a,
            output_file
        ]

    else:  # mp4
        # MP4 branch: H.264 with specific bitrate settings, yadif, faststart, AAC audio
        vf_chain = []
        if hd:
            vf_chain += [
                "colormatrix=bt601:bt709",
                "scale=1440:1080:flags=lanczos",
                "pad=1920:1080:240:0"
            ]
        vf_chain += [
            "yadif",
            fade_v_in,
            fade_v_out
        ]
        vf = ",".join(vf_chain)

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time), "-to", str(end_time),
            "-i", input_file,
            "-map", "0:v", "-map", "0:a",
            "-c:v", "libx264",
            "-movflags", "faststart",
            "-pix_fmt", "yuv420p",
            "-crf", "21",
            "-vf", vf,
            "-c:a", "aac",
            "-b:a", "320000",
            "-ar", "48000",
            "-af", fade_a,
            output_file
        ]

    subprocess.call(cmd)

def to_seconds(ts: str) -> int:
    h, m, s = map(int, ts.split(":"))
    return h * 3600 + m * 60 + s

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Trim and transcode to ProRes or MP4, with optional HD up-res & pillarbox."
    )
    parser.add_argument("-f", "--file", required=True,
                        help="Input media file")
    parser.add_argument("-o", "--output", required=True,
                        help="Output directory")
    parser.add_argument("-t", "--timestamp", required=True, nargs=2,
                        metavar=("START","END"),
                        help="Start & end times (HH:MM:SS)")
    parser.add_argument("--HD", action="store_true",
                        help="Up-res & pillarbox to 1080p (scale→1440×1080 pad→1920×1080)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prores", action="store_true",
                       help="Produce a ProRes .mov (PCM s24le audio)")
    group.add_argument("--mp4", action="store_true",
                       help="Produce an H.264 MP4 (AAC audio @320k, faststart)")

    args = parser.parse_args()

    start_sec = to_seconds(args.timestamp[0])
    end_sec   = to_seconds(args.timestamp[1])

    transcode_file(
        input_file=args.file,
        output_dir=args.output,
        start_time=start_sec,
        end_time=end_sec,
        hd=args.HD,
        prores=args.prores,
        mp4=args.mp4
    )
