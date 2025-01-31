#!/usr/bin/env python3

import argparse
import os
import subprocess
import json
import hashlib
import logging
from pathlib import Path
from pymediainfo import MediaInfo

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def is_bag(directory):
    """
    Check that a directory has the required BagIt metadata files.
    """
    required = ['bag-info.txt', 'bagit.txt', 'manifest-md5.txt', 'tagmanifest-md5.txt']
    return all((Path(directory) / fname).exists() for fname in required)

def get_video_resolution(input_file):
    """
    Get the width and height of a video file using ffprobe.
    Returns (width, height) as integers.
    """
    ffprobe_command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", input_file
    ]

    try:
        result = subprocess.run(ffprobe_command, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split(","))
        return width, height
    except Exception as e:
        logging.error(f"Error detecting resolution for {input_file}: {e}")
        raise ValueError(f"Could not determine resolution for {input_file}")

def remake_scs_from_pm(bag_path):
    """
    Create new Service Copy MP4 files from the Preservation Master MKV.
    - If NTSC (720x486), applies deinterlacing, crops to 720x480, and sets DAR 4:3.
    - If PAL (720x576), applies deinterlacing but no cropping.
    Returns a list of the newly updated SC .mp4 paths.
    """
    modified_files = []
    servicecopies_dir = Path(bag_path) / 'data' / 'ServiceCopies'
    pm_dir = Path(bag_path) / 'data' / 'PreservationMasters'

    for sc_file in servicecopies_dir.glob('*_sc.mp4'):
        pm_basename = sc_file.name.replace('_sc.mp4', '_pm.mkv')
        pm_file = pm_dir / pm_basename

        if pm_file.is_file():
            logging.info(f"Transcoding new SC from PM: {pm_file} -> {sc_file}")
            temp_filepath = sc_file.with_suffix('.temp.mp4')

            # Detect resolution and decide cropping
            try:
                width, height = get_video_resolution(str(pm_file))
            except ValueError as e:
                logging.error(e)
                continue

            if width == 720 and height == 486:  # NTSC
                video_filter = "idet,bwdif=1,crop=w=720:h=480:x=0:y=4,setdar=4/3"
            elif width == 720 and height == 576:  # PAL
                video_filter = "idet,bwdif=1"
            else:
                logging.warning(f"Unknown resolution {width}x{height}. Skipping cropping.")
                video_filter = "idet,bwdif=1"

            cmd = [
                "ffmpeg",
                "-i", str(pm_file),
                "-c:v", "libx264",
                "-movflags", "faststart",
                "-pix_fmt", "yuv420p",
                "-crf", "21",
                "-vf", video_filter,
                "-c:a", "aac",
                "-b:a", "320000", 
                "-ar", "48000",
                str(temp_filepath)
            ]
            subprocess.run(cmd, check=True)

            os.remove(sc_file)
            os.rename(temp_filepath, sc_file)
            modified_files.append(str(sc_file))
        else:
            logging.warning(f"No Preservation Master found for {sc_file}. Expected: {pm_file}")

    return modified_files

def remake_scs_from_sc(bag_path):
    """
    Create new Service Copy MP4 files from existing Service Copy MP4 files.
    Returns a list of the newly updated SC .mp4 paths.
    """
    modified_files = []
    servicecopies_dir = Path(bag_path) / 'data' / 'ServiceCopies'

    for sc_file in servicecopies_dir.glob('*_sc.mp4'):
        logging.info(f"Re-transcoding existing SC file for anamorphic fix: {sc_file}")
        temp_filepath = sc_file.with_suffix('.temp.mp4')

        cmd = [
            "ffmpeg",
            "-i", str(sc_file),
            "-c:v", "libx264",
            "-movflags", "faststart",
            "-pix_fmt", "yuv420p",
            "-crf", "21",
            "-vf", "setdar=16/9",
            "-c:a", "copy",
            str(temp_filepath)
        ]
        subprocess.run(cmd, check=True)

        os.remove(sc_file)
        os.rename(temp_filepath, sc_file)
        modified_files.append(str(sc_file))

    return modified_files

def modify_json(data_dir):
    """
    Update metadata in all *_sc.json sidecar files within `data_dir`.
    - dateCreated (from file_last_modification_date)
    - fileSize (in bytes)
    Returns a list of JSON files that were updated.
    """
    modified_json_files = []

    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith('_sc.json'):
                json_path = os.path.join(root, file)
                sc_mp4_path = os.path.join(root, file.replace('_sc.json', '_sc.mp4'))

                # Check if the .mp4 actually exists
                if not os.path.exists(sc_mp4_path):
                    logging.warning(f"Skipping {json_path}; no corresponding SC MP4 found.")
                    continue

                logging.info(f"Updating sidecar JSON: {json_path}")
                media_info = MediaInfo.parse(sc_mp4_path)
                general_tracks = [t for t in media_info.tracks if t.track_type == "General"]
                if not general_tracks:
                    logging.warning(f"No 'General' track found in {sc_mp4_path}.")
                    continue

                general_data = general_tracks[0].to_data()
                date_created = general_data.get('file_last_modification_date', '')
                file_size = general_data.get('file_size', '0')

                with open(json_path, 'r+', encoding='utf-8-sig') as jf:
                    data = json.load(jf)
                    # Safely navigate the JSON structure; adjust as needed
                    if "technical" in data:
                        data["technical"]["dateCreated"] = date_created.split(' ')[0] if date_created else ""
                        if "fileSize" in data["technical"]:
                            data["technical"]["fileSize"]["measure"] = int(file_size)
                        else:
                            # If "fileSize" doesn't exist, create it
                            data["technical"]["fileSize"] = {"measure": int(file_size), "unit": "bytes"}
                    # Overwrite JSON
                    jf.seek(0)
                    json.dump(data, jf, indent=4)
                    jf.truncate()

                modified_json_files.append(json_path)

    return modified_json_files

def calculate_md5(file_path):
    """
    Return the MD5 checksum for the file at file_path.
    """
    logging.info(f"Calculating MD5 for: {file_path}")
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def update_manifests(bag_path, modified_paths):
    """
    Update manifest-md5.txt checksums for each file in `modified_paths`.
    Then update the tagmanifest-md5.txt with the new manifest-md5.txt checksum.
    `modified_paths` should be relative to bag_path.
    """
    manifest_path = Path(bag_path) / 'manifest-md5.txt'
    tag_manifest_path = Path(bag_path) / 'tagmanifest-md5.txt'

    # 1) Update manifest-md5.txt
    if manifest_path.exists():
        with manifest_path.open('r') as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            parts = line.strip().split(' ', 1)
            if len(parts) != 2:
                new_lines.append(line)
                continue
            old_checksum, rel_path = parts
            rel_path = rel_path.strip()
            if rel_path in modified_paths:
                full_path = os.path.join(bag_path, rel_path)
                if os.path.isfile(full_path):
                    new_checksum = calculate_md5(full_path)
                    new_line = f"{new_checksum} {rel_path}\n"
                    new_lines.append(new_line)
                else:
                    logging.warning(f"Could not find file for manifest update: {full_path}")
                    new_lines.append(line)
            else:
                new_lines.append(line)

        with manifest_path.open('w') as f:
            f.write(''.join(new_lines))

    # 2) Update tagmanifest-md5.txt for the changed manifest
    if tag_manifest_path.exists() and manifest_path.exists():
        with tag_manifest_path.open('r') as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            parts = line.strip().split(' ', 1)
            if len(parts) != 2:
                new_lines.append(line)
                continue
            old_checksum, file_ref = parts
            if 'manifest-md5.txt' in file_ref:
                # Recalculate the manifest's MD5
                new_manifest_md5 = calculate_md5(manifest_path)
                new_line = f"{new_manifest_md5} {file_ref}\n"
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        with tag_manifest_path.open('w') as f:
            f.write(''.join(new_lines))

def update_payload_oxum(bag_path):
    """
    Recalculate Payload-Oxum (total size in bytes . number of files) for all files under data/.
    Update bag-info.txt accordingly.
    """
    data_path = Path(bag_path) / 'data'
    bag_info_path = Path(bag_path) / 'bag-info.txt'

    total_size = 0
    total_files = 0

    for file in data_path.rglob('*'):
        if file.is_file():
            total_size += file.stat().st_size
            total_files += 1

    new_oxum = f"{total_size}.{total_files}"
    logging.info(f"Calculated new Payload-Oxum: {new_oxum}")

    if bag_info_path.exists():
        with bag_info_path.open('r') as f:
            lines = f.readlines()

        new_lines = []
        found_oxum = False
        for line in lines:
            if line.startswith('Payload-Oxum:'):
                new_lines.append(f'Payload-Oxum: {new_oxum}\n')
                found_oxum = True
            else:
                new_lines.append(line)

        # If there wasn't a Payload-Oxum line, add it
        if not found_oxum:
            new_lines.append(f'Payload-Oxum: {new_oxum}\n')

        with bag_info_path.open('w') as f:
            f.write(''.join(new_lines))

def update_tagmanifest(bag_path):
    """
    Update the tagmanifest-md5.txt to capture any changes to:
      - bag-info.txt
      - manifest-md5.txt
    """
    tag_manifest_path = Path(bag_path) / 'tagmanifest-md5.txt'
    bag_info_path = Path(bag_path) / 'bag-info.txt'
    manifest_path = Path(bag_path) / 'manifest-md5.txt'

    if not tag_manifest_path.exists():
        return

    with tag_manifest_path.open('r') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        parts = line.strip().split(' ', 1)
        if len(parts) != 2:
            new_lines.append(line)
            continue
        old_checksum, filename = parts

        # If the line references manifest-md5.txt, recalc and replace
        if 'manifest-md5.txt' in filename and manifest_path.exists():
            new_manifest_md5 = calculate_md5(manifest_path)
            new_line = f"{new_manifest_md5} {filename}\n"
            new_lines.append(new_line)
        # If the line references bag-info.txt, recalc and replace
        elif 'bag-info.txt' in filename and bag_info_path.exists():
            new_baginfo_md5 = calculate_md5(bag_info_path)
            new_line = f"{new_baginfo_md5} {filename}\n"
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    with tag_manifest_path.open('w') as f:
        f.write(''.join(new_lines))

    logging.info("tagmanifest-md5.txt updated successfully.")

def main():
    parser = argparse.ArgumentParser(
        description='Remake or fix Service Copy MP4 files in BagIt packages'
    )
    parser.add_argument('-d', '--directory', required=True,
                        help='Directory containing BagIt packages')
    parser.add_argument('--source', choices=['pm', 'sc'], default='pm',
                        help=("Choose the source for re-encoding service copies: "
                              "'pm' for Preservation Master MKV (default), "
                              "'sc' for the existing service copy MP4."))

    args = parser.parse_args()
    top_dir = Path(args.directory)

    for bag_name in os.listdir(top_dir):
        bag_path = top_dir / bag_name
        if bag_path.is_dir() and is_bag(bag_path):
            logging.info(f"Processing BagIt bag: {bag_path}")

            # 1) Depending on the --source argument, re-encode from PM or SC
            if args.source == 'sc':
                sc_modified = remake_scs_from_sc(bag_path)
            else:
                sc_modified = remake_scs_from_pm(bag_path)

            # 2) Update sidecar JSON. 
            #    This might modify a few JSON files that also need fresh checksums.
            json_modified = modify_json(bag_path / 'data')

            # 3) Combine the newly modified files
            #    We need their paths relative to the bag root for manifest updates.
            all_modified = sc_modified + json_modified
            rel_modified = [
                os.path.relpath(path, start=bag_path).replace('\\', '/')
                for path in all_modified
            ]

            # 4) Update the payload manifest
            update_manifests(bag_path, rel_modified)

            # 5) Recalculate the Payload-Oxum in bag-info.txt
            update_payload_oxum(bag_path)

            # 6) Update the tagmanifest checksums for bag-info.txt & manifest-md5.txt
            update_tagmanifest(bag_path)

if __name__ == "__main__":
    main()
