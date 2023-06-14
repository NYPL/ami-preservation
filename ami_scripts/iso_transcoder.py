#!/usr/bin/env python3

import argparse
from pathlib import Path
import os
import subprocess
import shutil
import logging
import tempfile
import sys
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def verify_mkvmerge_installation():
    try:
        result = subprocess.run(["mkvmerge", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("mkvmerge is not installed on this system. Please install mkvtoolnix (brew install mkvtoolnix).")
        sys.exit(1)
    except FileNotFoundError:
        print("mkvmerge is not found in your system's path. Please make sure mkvtoolnix is installed and mkvmerge is accessible.")
        sys.exit(1)


def mount_Image(ISO_Path):
    logging.info(f"Mounting ISO image {ISO_Path}")
    user_home = Path.home()
    mount_base_dir = user_home / "iso_mounts"
    mount_base_dir.mkdir(parents=True, exist_ok=True)

    for mount_increment in range(1<<30):  # limit to avoid potential infinite loop
        mount_point = mount_base_dir / f"ISO_Volume_{mount_increment}"
        if not mount_point.exists():
            break

    mount_point.mkdir(parents=True, exist_ok=True)

    mount_command = ["hdiutil", "attach", str(ISO_Path), "-mountpoint", str(mount_point)]

    try:
        subprocess.run(mount_command, check=True)
        logging.info(f"Mounted ISO image {ISO_Path} at {mount_point}")
        time.sleep(3)  # wait for 3 seconds
        return mount_point
    except subprocess.CalledProcessError:
        logging.error("Mounting failed due to subprocess error. Try running script in sudo mode")
        quit()
    except Exception as e:
        logging.error(f"Mounting failed. Error: {e}")
        quit()


def unmount_Image(mount_point):
    logging.info(f"Attempting to unmount {mount_point}")
    unmount_command = ["hdiutil", "detach", str(mount_point)]

    for attempt in range(5):  # try up to 5 times
        try:
            subprocess.run(unmount_command, check=True)
            # Allow some time for the unmount command to fully complete
            time.sleep(3)

            # Try to remove the mount point directory, with retry logic
            for rm_attempt in range(5):
                try:
                    shutil.rmtree(str(mount_point.parent))
                    logging.info(f"Unmounted and removed mount point: {mount_point}")
                    return True
                except OSError:
                    logging.error(f"Failed to remove mount point: {mount_point}. Retrying in 3 seconds...")
                    time.sleep(3)

            logging.error(f"Failed to remove mount point: {mount_point} after 5 attempts")
            return False
        except subprocess.CalledProcessError:
            logging.error(f"Unmounting failed due to subprocess error for {mount_point}. Retrying in 3 seconds...")
            time.sleep(3)  # wait for 3 seconds before retrying

    logging.error(f"Failed to unmount {mount_point} after 5 attempts")
    return False


def get_vob_files(mount_point, split=False):
    input_vobList = []
    input_discList = []
    lastDiscNum = 1

    # Walk through all directories and subdirectories in mount_point
    for root, dirs, files in os.walk(mount_point):
        for file in files:
            # Check if the file is a VOB file and starts with "VTS"
            if file.endswith(".VOB") and file != "VIDEO_TS.VOB" and file.split("_")[0] == "VTS":
                discNum = file.split("_")[1]
                discNumInt = int(discNum.split(".")[0])
                vobNum = file.split("_")[-1]
                vobNumInt = int(vobNum.split(".")[0])
                if discNumInt == lastDiscNum:
                    if vobNumInt > 0:
                        input_vobList.append(os.path.join(root, file))
                if discNumInt > lastDiscNum:
                    input_vobList.sort()
                    input_discList.append(input_vobList)
                    input_vobList = []
                    if vobNumInt > 0:
                        input_vobList.append(os.path.join(root, file))
                lastDiscNum = discNumInt

    if input_vobList:
        input_vobList.sort()
        input_discList.append(input_vobList)

    if split:
        return [file for sublist in input_discList for file in sublist]
    else:
        return input_discList


def transcode_vobs(iso_path, output_directory, split, force_concat):
    logging.info(f"Transcoding VOB files from {iso_path}")
    mount_point = mount_Image(iso_path)
    vob_files = get_vob_files(mount_point, split)

    iso_basename = iso_path.stem.replace("_pm", "")
    if force_concat:
        # Concatenate all VOB files and transcode
        try:
            with tempfile.NamedTemporaryFile(suffix=".vob", delete=False) as tmp_vob_file:
                cat_command = ["cat"] + [str(vob_file) for disc_vob_files in vob_files for vob_file in disc_vob_files]
                with open(tmp_vob_file.name, 'wb') as outfile:  # use 'wb' because we're working with binary files
                    logging.info(f"Concatenating VOB files to {tmp_vob_file.name}")
                    subprocess.run(cat_command, stdout=outfile, check=True)

                output_file = output_directory / f"{iso_basename}_sc.mp4"
                channel_layout = get_channel_layout(tmp_vob_file.name)
                resolution = get_resolution(tmp_vob_file.name)
                ffmpeg_command = build_ffmpeg_command(tmp_vob_file.name, output_file, channel_layout)

                if resolution not in ['720x480', '720x576']:
                    vf_index = ffmpeg_command.index('-vf')
                    ffmpeg_command[vf_index + 1] += ',scale=720:480'

                logging.info(f"Transcoding concatenated VOB file to {output_file}")
                try:
                    subprocess.run(ffmpeg_command, check=True)
                except subprocess.CalledProcessError:
                    logging.error(f"Transcoding failed for {tmp_vob_file.name} due to subprocess error")
                    raise Exception("Transcoding failed")
        except Exception as e:
            logging.warning(f"Either concatenation or transcoding failed with 'cat'. Error: {e}")
            os.remove(tmp_vob_file.name)  # delete the previous failed file
            try:
                with tempfile.NamedTemporaryFile(suffix=".mkv", delete=False) as tmp_vob_file:
                    for disc_vob_files in vob_files:
                        try:
                            mkvmerge_command = ["mkvmerge", "-o", tmp_vob_file.name, str(disc_vob_files[0])]
                            for vob_file in disc_vob_files[1:]:
                                mkvmerge_command.extend(["+", str(vob_file)])
                            subprocess.run(mkvmerge_command, check=True)
                        except subprocess.CalledProcessError:
                            logging.warning(f"Concatenating failed for {disc_vob_files} with mkvmerge, but continuing anyway.")

                    output_file = output_directory / f"{iso_basename}_sc.mp4"
                    channel_layout = get_channel_layout(tmp_vob_file.name)
                    resolution = get_resolution(tmp_vob_file.name)
                    ffmpeg_command = build_ffmpeg_command(tmp_vob_file.name, output_file, channel_layout)

                    if resolution not in ['720x480', '720x576']:
                        vf_index = ffmpeg_command.index('-vf')
                        ffmpeg_command[vf_index + 1] += ',scale=720:480'

                    logging.info(f"Transcoding concatenated VOB file to {output_file}")
                    try:
                        subprocess.run(ffmpeg_command, check=True)
                    except subprocess.CalledProcessError:
                        logging.error(f"Transcoding failed for {tmp_vob_file.name} due to subprocess error")
                        raise Exception("Transcoding failed")
            except Exception as e:
                logging.error(f"Concatenating failed for {disc_vob_files} with mkvmerge too.")
                os.remove(tmp_vob_file.name)  # delete the failed file
                raise Exception("Both concatenation methods failed.")

    else:
        disc_count = 1
        if split:
            # Transcode each VOB file separately
            for vob_file in vob_files:  # vob_files is a list of file paths (strings)
                output_file = output_directory / f"{iso_basename}r{str(disc_count).zfill(2)}_sc.mp4"
                logging.info(f"Transcoding VOB file {vob_file} to {output_file}")
                channel_layout = get_channel_layout(vob_file)
                resolution = get_resolution(tmp_vob_file.name)

                ffmpeg_command = build_ffmpeg_command(vob_file, output_file, channel_layout)
                if resolution not in ['720x480', '720x576']:
                    vf_index = ffmpeg_command.index('-vf')
                    ffmpeg_command[vf_index + 1] += ',scale=720:480'

                try:
                    subprocess.run(ffmpeg_command, check=True)
                except subprocess.CalledProcessError:
                    logging.error(f"Transcoding failed for {vob_file} due to subprocess error")
                except Exception as e:
                    logging.error(f"Transcoding failed for {vob_file}. Error: {e}")
                disc_count += 1
        else:
            for disc_vob_files in vob_files:  # disc_vob_files is a list of file paths (strings)
                tmp_vob_file = None
                mkvmerge_used = False
                while True:
                    try:
                        if not mkvmerge_used:
                            with tempfile.NamedTemporaryFile(suffix=".vob", delete=False) as tmp_vob_file:
                                cat_command = ["cat"] + disc_vob_files
                                with open(tmp_vob_file.name, 'wb') as outfile:  # use 'wb' because we're working with binary files
                                    logging.info(f"Concatenating VOB files to {tmp_vob_file.name}")
                                    subprocess.run(cat_command, stdout=outfile, check=True)
                        else:
                            try:
                                with tempfile.NamedTemporaryFile(suffix=".mkv", delete=False) as tmp_vob_file:
                                    mkvmerge_command = ["mkvmerge", "-o", tmp_vob_file.name]
                                    for vob_file in disc_vob_files[:-1]:
                                        mkvmerge_command.extend([vob_file, "+"])
                                    mkvmerge_command.append(disc_vob_files[-1])
                                    subprocess.run(mkvmerge_command, check=True)
                            except subprocess.CalledProcessError:
                                logging.warning("MKVMerge failed, but proceeding to FFmpeg")
                    except subprocess.CalledProcessError:
                        logging.warning(f"Concatenation failed for {disc_vob_files}. Trying alternative method.")
                        if tmp_vob_file is not None:
                            os.remove(tmp_vob_file.name)  # delete the previous failed file
                            tmp_vob_file = None
                        if mkvmerge_used:
                            logging.error(f"Concatenation failed for {disc_vob_files} with both methods.")
                            raise Exception("Both concatenation methods failed.")
                        else:
                            mkvmerge_used = True
                            continue

                    output_file = output_directory / f"{iso_basename}r{str(disc_count).zfill(2)}_sc.mp4" if len(vob_files) > 1 else output_directory / f"{iso_basename}_sc.mp4"
                    channel_layout = get_channel_layout(tmp_vob_file.name)
                    resolution = get_resolution(tmp_vob_file.name)

                    ffmpeg_command = build_ffmpeg_command(tmp_vob_file.name, output_file, channel_layout)
                    if resolution not in ['720x480', '720x576']:
                        vf_index = ffmpeg_command.index('-vf')
                        ffmpeg_command[vf_index + 1] += ',scale=720:480'

                    logging.info(f"Transcoding concatenated VOB file to {output_file}")
                    try:
                        subprocess.run(ffmpeg_command, check=True)
                    except subprocess.CalledProcessError:
                        logging.error(f"Transcoding failed for {tmp_vob_file.name} due to subprocess error")
                        if mkvmerge_used:
                            # if mkvmerge was already used for concatenation, raise an exception
                            raise
                        else:
                            # if mkvmerge was not yet used for concatenation, set the flag and try again
                            logging.info("Will retry with mkvmerge concatenation.")
                            mkvmerge_used = True
                            continue
                    except Exception as e:
                        logging.error(f"Transcoding failed for {tmp_vob_file.name}. Error: {e}")

                    disc_count += 1
                    os.remove(tmp_vob_file.name)  # remove the temp file
                    break  # break the while loop when everything is successful

    logging.info(f"Unmounting {mount_point}")
    if not unmount_Image(mount_point):
        logging.error(f"Skipping {iso_path} due to unmounting error in previous ISO.")
        
        return


def get_channel_layout(vob_file):
    ffprobe_command = [
        "ffprobe", "-v", "error", "-select_streams", "a", 
        "-show_entries", "stream=channel_layout", 
        "-of", "csv=p=0", vob_file
    ]

    # Run the command and get the output
    output = subprocess.run(ffprobe_command, text=True, capture_output=True).stdout.strip()

    # Check if the channel layout is 4 channels (FL+FR+LFE+BC)
    if output == "4 channels (FL+FR+LFE+BC)":
        return "4.0"
    else:
        return None

def get_resolution(vob_file):
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", vob_file]
    try:
        output = subprocess.check_output(command).decode().strip().rstrip('x')
    except subprocess.CalledProcessError:
        return None
    return output

def build_ffmpeg_command(input_file, output_file, channel_layout):
    ffmpeg_command = [
        "ffmpeg", "-i", str(input_file),
        "-c:v", "libx264",
        "-movflags", "faststart",
        "-pix_fmt", "yuv420p",
        "-b:v", "3500000",
        "-bufsize", "1750000",
        "-maxrate", "3500000",
        "-vf", "yadif",
        "-c:a", "aac",
        "-b:a", "320000",
        "-ar", "48000"
    ]

    # Add the channelmap filter if needed
    if channel_layout is not None:
        ffmpeg_command += ["-filter:a", f"channelmap=channel_layout={channel_layout}"]

    ffmpeg_command.append(str(output_file))

    return ffmpeg_command



def verify_transcoding(iso_paths, output_directory):
    for iso_path in iso_paths:
        iso_basename = os.path.splitext(os.path.basename(iso_path))[0]
        iso_basename = iso_basename.replace("_pm", "")
        expected_output_files = [file for file in os.listdir(output_directory) if file.startswith(iso_basename) and file.endswith('.mp4')]

        if not expected_output_files:
            logging.error(f"No MP4 files were created for ISO: {iso_path}")
        else:
            logging.info(f"{len(expected_output_files)} MP4 files were created for ISO: {iso_path}")


def main():
    parser = argparse.ArgumentParser(description='Transcode VOB files from ISO images to H.264 MP4s.')
    parser.add_argument('-i', '--input', dest='i', help='the path to the input directory or files')
    parser.add_argument('-o', '--output', dest='o', help='the output file path (optional, defaults to the same as the input)')
    parser.add_argument('-s', '--split', action='store_true', default=False, help='split each VOB into a separate MP4 (optional, defaults to concatenating VOBs)')
    parser.add_argument('-f', '--force-concat', action='store_true', default=False, help='force concatenating all VOBs into one MP4 (optional)')
    args = parser.parse_args()

    verify_mkvmerge_installation()

    input_directory = Path(args.i)
    output_directory = Path(args.o) if args.o else input_directory
    split = args.split
    force_concat = args.force_concat if 'force_concat' in args else False

    output_directory.mkdir(parents=True, exist_ok=True)

    iso_files = list(sorted(input_directory.glob('*.iso')))  # Create a list to hold all ISO paths
    for iso_file in iso_files:
        try:
            transcode_vobs(iso_file, output_directory, split, force_concat)
        except Exception as e:
            logging.error(e)
            continue


    # Call verify_transcoding after all ISOs are transcoded
    verify_transcoding(iso_files, output_directory)


if __name__ == "__main__":
    main()

