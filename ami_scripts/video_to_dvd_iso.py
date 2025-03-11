#!/usr/bin/env python3
import argparse
import subprocess
import json
import os
from fractions import Fraction

def probe_video_format(input_file):
    """
    Uses ffprobe to inspect the input video and decide if it is NTSC or PAL.
    It first looks at the video height and then the frame rate.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=height,avg_frame_rate",
        "-of", "json",
        input_file
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print("Error running ffprobe:", e.stderr)
        exit(1)
    info = json.loads(result.stdout)
    if "streams" not in info or len(info["streams"]) == 0:
        print("No video stream found in the file.")
        exit(1)
    stream = info["streams"][0]
    height = stream.get("height")
    avg_frame_rate = stream.get("avg_frame_rate")
    video_format = None

    if height is not None:
        # If height is exactly 480 or 576, that's a clear indicator.
        if height == 480:
            video_format = "ntsc"
        elif height == 576:
            video_format = "pal"
        else:
            # Fallback: if height is below 500 assume NTSC; else PAL.
            video_format = "ntsc" if height < 500 else "pal"
    else:
        # If height is missing, use avg_frame_rate.
        try:
            if avg_frame_rate and avg_frame_rate != "0/0":
                fr = float(Fraction(avg_frame_rate))
                if abs(fr - 29.97) < 1:
                    video_format = "ntsc"
                elif abs(fr - 25) < 1:
                    video_format = "pal"
                else:
                    video_format = "ntsc"  # default
            else:
                video_format = "ntsc"
        except Exception as e:
            video_format = "ntsc"
    print(f"Determined video format: {video_format.upper()} (height: {height}, frame rate: {avg_frame_rate})")
    return video_format

def transcode_video(input_file, video_format):
    """
    Uses ffmpeg to transcode the input file to a DVD-compliant MPEG-2 file.
    """
    target = "ntsc-dvd" if video_format == "ntsc" else "pal-dvd"
    output_file = "dvd_compliant.mpg"
    cmd = ["ffmpeg", "-i", input_file, "-target", target, output_file]
    print("Running ffmpeg command:")
    print(" ".join(cmd))
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        print("Error: ffmpeg transcoding failed.")
        exit(1)
    return output_file

def author_dvd_structure(mpg_file, video_format):
    """
    Uses dvdauthor to create the DVD structure (VIDEO_TS, AUDIO_TS, etc.).
    The VIDEO_FORMAT environment variable is set based on the detected format.
    """
    # Set the environment variable (NTSC or PAL)
    os.environ["VIDEO_FORMAT"] = video_format.upper()
    # Chapters string (as given in your instructions)
    chapters = ("0,5:00,10:00,15:00,20:00,25:00,30:00,35:00,40:00,45:00,50:00,55:00,"
                "1:00:00,1:05:00,1:10:00,1:15:00,1:20:00,1:25:00,1:30:00,1:35:00,"
                "1:40:00,1:45:00,1:50:00,1:55:00,2:00:00,2:05:00,2:10:00,2:15:00,"
                "2:20:00,2:25:00,2:30:00,2:35:00,2:40:00,2:45:00")
    # Create the DVD structure with chapter markers
    cmd1 = ["dvdauthor", "-o", "dvd_structure", "-t", "-c", chapters, mpg_file]
    print("Running dvdauthor command (creating structure):")
    print(" ".join(cmd1))
    try:
        subprocess.check_call(cmd1)
    except subprocess.CalledProcessError:
        print("Error: dvdauthor (creating structure) failed.")
        exit(1)
    # Finalize the DVD structure
    cmd2 = ["dvdauthor", "-o", "dvd_structure", "-T"]
    print("Running dvdauthor command (finalizing):")
    print(" ".join(cmd2))
    try:
        subprocess.check_call(cmd2)
    except subprocess.CalledProcessError:
        print("Error: dvdauthor (finalizing) failed.")
        exit(1)

def create_iso(dvd_title, iso_filename):
    """
    Uses mkisofs to create a DVD-compliant ISO image.
    """
    cmd = ["mkisofs", "-dvd-video", "-V", dvd_title, "-o", iso_filename, "dvd_structure"]
    print("Running mkisofs command:")
    print(" ".join(cmd))
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        print("Error: mkisofs failed.")
        exit(1)
    return iso_filename

def main():
    parser = argparse.ArgumentParser(description="Create a DVD-compliant ISO disc image from a video file.")
    parser.add_argument("-i", "--input", required=True, help="Path to the input video file")
    parser.add_argument("-t", "--title", default="MyDVDTitle", help="DVD Title for the ISO image (default: MyDVDTitle)")
    args = parser.parse_args()
    
    input_file = args.input
    dvd_title = args.title

    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' does not exist.")
        exit(1)

    # Determine output ISO filename based on input file name.
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    iso_filename = base_name + ".iso"

    # Step 1: Determine if the video is NTSC or PAL
    video_format = probe_video_format(input_file)

    # Step 2: Transcode the source video to a DVD-compliant MPEG-2 file
    mpg_file = transcode_video(input_file, video_format)

    # Step 3: Author the DVD structure using dvdauthor
    author_dvd_structure(mpg_file, video_format)

    # Step 4: Create the ISO image with mkisofs
    create_iso(dvd_title, iso_filename)
    print(f"\nDVD ISO image created successfully: {iso_filename}")

if __name__ == "__main__":
    main()
