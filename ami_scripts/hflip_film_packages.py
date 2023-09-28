#!/usr/bin/env python3

import argparse
import os
import json
import subprocess
import time
import shutil
from pymediainfo import MediaInfo
import re


def is_bag(directory):
    return all(os.path.exists(os.path.join(directory, fname)) for fname in ['bag-info.txt', 'bagit.txt', 'manifest-md5.txt', 'tagmanifest-md5.txt'])

def hflip_videos(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            print(f"Checking file: {filepath}")

            if file.endswith('mz.mov'):
                print(f"Processing mz.mov file: {filepath}")
                temp_filepath = filepath + ".temp.mov"
                command = [
                    "ffmpeg",
                    "-i", filepath,
                    "-vf", "hflip",
                    "-c:v", "prores",
                    "-profile:v", "3",
                    "-c:a", "copy",
                    temp_filepath
                ]
                subprocess.run(command)
                os.remove(filepath)
                os.rename(temp_filepath, filepath)

            elif file.endswith('sc.mp4'):
                print(f"Processing sc.mp4 file: {filepath}")
                temp_filepath = filepath + ".temp.mp4"
                command = [
                    "ffmpeg",
                    "-i", filepath,
                    "-vf", "hflip",
                    "-c:v", "libx264",
                    "-movflags", "faststart",
                    "-pix_fmt", "yuv420p",
                    "-b:v", "8000000",
                    "-bufsize", "5000000",
                    "-maxrate", "8000000",
                    "-c:a", "copy",
                    temp_filepath
                ]
                subprocess.run(command)
                os.remove(filepath)
                os.rename(temp_filepath, filepath)

            else:
                print(f"Skipping unknown file type: {filepath}")


def modify_json(directory):
    append_text = "Film scanned with incorrect horizontal orientation; FFmpeg hflip filter used to flip Mezzanine and Service Copies (Preservation Master files left untouched)."
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.json'):
                media_file = file.replace("_mz.json", "_mz.mov").replace("_sc.json", "_sc.mp4").replace("_pm.json", "_pm.mkv")
                media_file_path = os.path.join(root, media_file)
                
                # Fetch media information using pymediainfo
                media_info = MediaInfo.parse(media_file_path)
                general_tracks = [t for t in media_info.tracks if t.track_type == "General"]
                
                if general_tracks:
                    general_data = general_tracks[0].to_data()

                    date_created = general_data.get('file_last_modification_date', '')
                    date_pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
                    match = date_pattern.search(date_created)
                    
                with open(os.path.join(root, file), 'r+') as json_file:
                    data = json.load(json_file)
                    
                    # Update dateCreated and fileSize based on MediaInfo
                    if general_tracks:
                        if match:
                            data['technical']['dateCreated'] = match.group(0)
                        else:
                            data['technical']['dateCreated'] = ''
                        data['technical']['fileSize']['measure'] = int(general_data.get('file_size', 0))

                    # Navigate to the nested structure
                    source = data.get("source", {})
                    notes = source.get("notes", {})
                    existing_text = notes.get("physicalConditionDigitizationNotes", "")
                    
                    # Append or add the new note
                    notes["physicalConditionDigitizationNotes"] = existing_text + ". " + append_text if existing_text else append_text

                    # Save back the modified notes to the data dictionary
                    source["notes"] = notes
                    data["source"] = source

                    # Write back to the JSON file
                    json_file.seek(0)
                    json.dump(data, json_file, indent=4)
                    json_file.truncate()


def unbag_and_rebag(directory):
    for item in ['bag-info.txt', 'bagit.txt', 'manifest-md5.txt', 'tagmanifest-md5.txt']:
        os.remove(os.path.join(directory, item))
    for subdir in ['Mezzanines', 'PreservationMasters', 'ServiceCopies']:
        source = os.path.join(directory, 'data', subdir)
        target = os.path.join(directory, subdir)
        os.rename(source, target)

    # Retry mechanism for removing 'data' directory
    max_retries = 5
    for _ in range(max_retries):
        try:
            shutil.rmtree(os.path.join(directory, 'data'))
            break  # if directory removal is successful, break out of the loop
        except OSError:
            time.sleep(5)  # wait for 5 seconds before retrying
    else:  # executed if the loop completed without breaking, indicating max retries hit
        print(f"Failed to remove 'data' directory in {directory} after {max_retries} attempts.")

    subprocess.run(["bagit.py", "--md5", directory])

def main():
    parser = argparse.ArgumentParser(description='Process BagIt packages.')
    parser.add_argument('-d', '--directory', required=True, help='Directory containing BagIt packages')
    args = parser.parse_args()

    for bag in os.listdir(args.directory):
        bag_path = os.path.join(args.directory, bag)
        if os.path.isdir(bag_path) and is_bag(bag_path):
            mezzanine_dir = os.path.join(bag_path, 'data', 'Mezzanines')
            servicecopy_dir = os.path.join(bag_path, 'data', 'ServiceCopies')

            print(f"Checking directory: {mezzanine_dir}")
            print(f"Checking directory: {servicecopy_dir}")

            hflip_videos(mezzanine_dir)
            hflip_videos(servicecopy_dir)

            modify_json(os.path.join(bag_path, 'data'))
            unbag_and_rebag(bag_path)


if __name__ == "__main__":
    main()
