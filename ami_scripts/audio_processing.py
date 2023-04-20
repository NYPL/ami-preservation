#!/usr/bin/env python3

import argparse
import subprocess
import shutil
import json
import os
import logging
import bagit
from pathlib import Path
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_args():
    parser = argparse.ArgumentParser(description='Transcode a directory of audio files')
    parser.add_argument('-s', '--source',
                        help='path to the source directory of audio files',
                        type=is_directory,
                        metavar='SOURCE_DIR',
                        required=True)
    parser.add_argument('-d', '--destination',
                        help='path to the output directory',
                        type=is_directory,
                        metavar='DEST_DIR',
                        required=True)
    return parser.parse_args()


def is_directory(path):
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"{path} is not a valid directory.")
    return Path(path)


def verify_directory(source_directory, destination_directory):
    if not source_directory.exists():
        raise FileNotFoundError(f"{source_directory} doesn't exist")
    if not source_directory.is_dir():
        raise NotADirectoryError(f"{source_directory} is not a directory")
    destination_directory.mkdir(parents=True, exist_ok=True)


def transcode_files(source_directory, destination_directory):
    files = skip_hidden_files(list(source_directory.glob("**/*.wav")))
    for file in tqdm(files, desc="Transcoding files", unit="file"):
        output_file = destination_directory / f"{file.stem}.flac"
        flac_command = [
            'flac', str(file),
            '--best',
            '--preserve-modtime',
            '--verify',
            '-o', str(output_file)
        ]
        return_code = subprocess.call(flac_command)
        if return_code != 0:
            logging.error(f"Error while transcoding {file}. Return code: {return_code}")
        else:
            logging.info(f"Successfully transcoded {file} to {output_file}")


def organize_files(source_directory, destination_directory):
    for file in skip_hidden_files(destination_directory.glob("*pm.flac")):
        id_folder = destination_directory / file.stem.split("_")[1]
        preservation_masters_dir = id_folder / "PreservationMasters"
        preservation_masters_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(file, preservation_masters_dir)

    for file in skip_hidden_files(destination_directory.glob("*em.flac")):
        id_folder = destination_directory / file.stem.split("_")[1]
        edit_masters_dir = id_folder / "EditMasters"
        edit_masters_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(file, edit_masters_dir)

    for file in skip_hidden_files(source_directory.glob("**/*.json")):
        id_folder = destination_directory / file.stem.split("_")[1]
        if "em.json" in file.name:
            edit_masters_dir = id_folder / "EditMasters"
            edit_masters_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, edit_masters_dir)
        elif "pm.json" in file.name:
            preservation_masters_dir = id_folder / "PreservationMasters"
            preservation_masters_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, preservation_masters_dir)

    for file in skip_hidden_files(source_directory.glob("**/*.cue")):
        id_folder = destination_directory / file.stem.split("_")[1]
        if "pm.cue" in file.name:
            preservation_masters_dir = id_folder / "PreservationMasters"
            preservation_masters_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, preservation_masters_dir)


def get_mediainfo(file_path, inform):
    result = subprocess.check_output(
        [
            'mediainfo',
            '--Language=raw',
            '--Full',
            f"--Inform={inform}",
            str(file_path),
        ]
    ).rstrip()
    return result.decode('UTF-8')


def update_flac_info(destination_directory):
    for flac_file in destination_directory.glob("**/*.flac"):
        json_file = next(flac_file.parent.glob(f"{flac_file.stem}.json"), None)

        if json_file is not None:
            with open(json_file) as f:
                data = json.load(f)

            date = get_mediainfo(flac_file, "General;%File_Modified_Date%").split(' ')[1]
            duration = get_mediainfo(flac_file, "General;%Duration%")
            human_duration = get_mediainfo(flac_file, "General;%Duration/String5%")
            flac_format = get_mediainfo(flac_file, "General;%Format%")
            codec = get_mediainfo(flac_file, "General;%Audio_Codec_List%")
            size = get_mediainfo(flac_file, "General;%FileSize%")

            data['asset']['referenceFilename'] = flac_file.name
            data['technical']['filename'] = flac_file.stem
            data['technical']['extension'] = flac_file.suffix[1:]  # Remove the leading period
            data['technical']['dateCreated'] = date
            data['technical']['durationMilli']['measure'] = duration
            data['technical']['durationHuman'] = human_duration
            data['technical']['fileFormat'] = flac_format
            data['technical']['audioCodec'] = codec
            data['technical']['fileSize']['measure'] = int(size)

            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)


def create_bag(destination_directory):
    bag_count = 0
    for id_folder in destination_directory.glob("*"):
        if id_folder.is_dir():
            bag = bagit.make_bag(str(id_folder), checksums=['md5'])
            print(f"Created BagIt bag for {id_folder}")
            bag_count += 1
    print(f"\nTotal bags created: {bag_count}")


def check_json_exists(destination_directory):
    missing_json_files = []
    for flac_file in destination_directory.glob("**/*.flac"):
        json_file = next(flac_file.parent.glob(f"{flac_file.stem}.json"), None)
        if json_file is None:
            missing_json_files.append(flac_file)
    
    if missing_json_files:
        print("Warning: The following FLAC files do not have corresponding JSON files:")
        for missing in missing_json_files:
            print(f"  {missing}")
        print()
    else:
        print("All FLAC files have corresponding JSON files.\n")


def check_pm_em_pairs(destination_directory):
    pm_files = sorted(destination_directory.glob("**/*pm.flac"))
    em_files = sorted(destination_directory.glob("**/*em.flac"))

    pm_stems = [pm.stem for pm in pm_files]
    em_stems = [em.stem for em in em_files]

    missing_pm_files = [em for em in em_stems if em.replace("_em", "_pm") not in pm_stems]
    missing_em_files = [pm for pm in pm_stems if pm.replace("_pm", "_em") not in em_stems]

    if missing_pm_files or missing_em_files:
        print("Warning: Some PM or EM files are missing:")
        if missing_pm_files:
            print("Missing PM files:")
            for missing_pm in missing_pm_files:
                print(f"  PM: {missing_pm.replace('_em', '_pm')}.flac")
        if missing_em_files:
            print("Missing EM files:")
            for missing_em in missing_em_files:
                print(f"  EM: {missing_em.replace('_pm', '_em')}.flac")
        print()
    else:
        print("All PM and EM file pairs match.\n")

def skip_hidden_files(files):
    return [file for file in files if not file.name.startswith("._")]

def main():
    args = get_args()
    source_directory = args.source
    destination_directory = args.destination

    # Create a new directory inside the destination_directory
    new_destination_directory = destination_directory / source_directory.name
    verify_directory(source_directory, new_destination_directory)
    
    transcode_files(source_directory, new_destination_directory)
    organize_files(source_directory, new_destination_directory)
    update_flac_info(new_destination_directory)
    
    create_bag(new_destination_directory)

    check_json_exists(new_destination_directory)
    check_pm_em_pairs(new_destination_directory)

if __name__ == '__main__':
    main()
