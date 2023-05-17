#!/usr/bin/env python3

import argparse
import os
import subprocess
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def mount_Image(ISO_Path):
    user_home = os.path.expanduser('~')
    mount_base_dir = os.path.join(user_home, "iso_mounts")
    os.makedirs(mount_base_dir, exist_ok=True)

    mount_point_exists = True
    mount_increment = 0

    while mount_point_exists:
        mount_point = "ISO_Volume_" + str(mount_increment)
        mount_point_exists = os.path.isdir(os.path.join(mount_base_dir, mount_point))
        mount_increment = mount_increment + 1

    mount_point = os.path.join(mount_base_dir, mount_point)

    try:
        mount_command = ["hdiutil", "attach", ISO_Path, "-mountpoint", mount_point]
        os.makedirs(mount_point, exist_ok=True)
        subprocess.run(mount_command, check=True)
        return mount_point
    except PermissionError:
        logging.error("Mounting failed due to permission error. Try running script in sudo mode")
        quit()
    except Exception as e:
        logging.error(f"Mounting failed. Error: {e}")
        quit()

def unmount_Image(mount_point):
    unmount_command = ["hdiutil", "detach", mount_point]
    subprocess.run(unmount_command, check=True)
    shutil.rmtree(os.path.dirname(mount_point))


def transcode_vobs(iso_path, output_directory):
    mount_point = mount_Image(iso_path)

    vob_files = []
    for root, dirs, files in os.walk(mount_point):
        for file in files:
            if file.endswith(".VOB") and file != "VIDEO_TS.VOB":
                vob_files.append(os.path.join(root, file))

    iso_basename = os.path.splitext(os.path.basename(iso_path))[0]
    iso_basename = iso_basename.replace("_pm", "")
    region_count = 1
    for vob_file in vob_files:
        output_file = os.path.join(output_directory, f"{iso_basename}r{str(region_count).zfill(2)}_sc.mp4")
        ffmpeg_command = ["ffmpeg", "-i", vob_file, "-c:v", "libx264", "-movflags", "faststart", "-pix_fmt", "yuv420p", "-b:v", "3500000", "-bufsize", "1750000", "-maxrate", "3500000", "-vf", "yadif", "-c:a", "aac", "-b:a", "320000", "-ar", "48000", output_file]
        try:
            subprocess.run(ffmpeg_command, check=True)
        except Exception as e:
            logging.error(f"Transcoding failed for {vob_file}. Error: {e}")
        region_count += 1

    unmount_Image(mount_point)

def main():
    parser = argparse.ArgumentParser(description='Transcode VOB files from ISO images to H.264 MP4s.')
    parser.add_argument('-i', '--input', dest='i', help='the path to the input directory or files')
    parser.add_argument('-o', '--output', dest='o', help='the output file path (optional, defaults to the same as the input)')
    args = parser.parse_args()

    input_directory = args.i
    output_directory = args.o or input_directory

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for iso_file in os.listdir(input_directory):
        if iso_file.endswith(".iso"):
            iso_path = os.path.join(input_directory, iso_file)
            transcode_vobs(iso_path, output_directory)

if __name__ == "__main__":
    main()
