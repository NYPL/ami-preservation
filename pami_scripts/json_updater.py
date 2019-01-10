#!/usr/bin/env python3

import argparse
import os
import subprocess
import bagit
import glob
import shutil
import json

def get_args():
    parser = argparse.ArgumentParser(description='Transcode a directory of video files')
    parser.add_argument('-s', '--source',
                        help = 'path to the source directory files', required=True)
    args = parser.parse_args()
    return args

def get_directory(args):
    try:
        test_directory = os.listdir(args.source)
    except OSError:
        exit('please retry with a valid directory of audio files')
    source_directory = args.source
    return source_directory

def get_info(source_directory):
    file_list = []
    json_list = []
    for root, dirs, files in os.walk(source_directory):
        for file in files:
            if file.endswith('.mp4'):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_list.append(item_path)
            if file.endswith('.json'):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                json_list.append(item_path)
    mediainfo_list = zip(sorted(file_list), sorted(json_list))
    for j_tuple in mediainfo_list:
        filename = j_tuple[0]
        media_json = j_tuple[1]
        name = filename.split('/')[-1]
        technicalFilename = name.split('.')[0]
        extension = name.split('.')[1]
        date_raw = subprocess.check_output(
            [
                'mediainfo', '--Language=raw',
                '--Full', "--Inform=General;%File_Modified_Date%",
                filename
            ]
            ).rstrip()
        date = str(date_raw).split(' ')[1]
        media_format = subprocess.check_output(
            [
                'mediainfo', '--Language=raw',
                '--Full', "--Inform=General;%Format%",
                filename
            ]
            ).rstrip()
        media_format = media_format.decode('UTF-8')
        codec = subprocess.check_output(
            [
                'mediainfo', '--Language=raw',
                '--Full', "--Inform=General;%Audio_Codec_List%",
                filename
            ]
            ).rstrip()
        codec = codec.decode('UTF-8')
        size = subprocess.check_output(
            [
                'mediainfo', '--Language=raw',
                '--Full', "--Inform=General;%FileSize%",
                filename
            ]
            ).rstrip()
        size = size.decode('UTF-8')
        with open(media_json, "r") as jsonFile:
            data = json.load(jsonFile)

        data['asset']['referenceFilename'] = name
        data['technical']['filename'] = technicalFilename
        data['technical']['extension'] = extension
        data['technical']['dateCreated'] = date
        data['technical']['fileFormat'] = media_format
        data['technical']['audioCodec'] = codec
        data['technical']['fileSize']['measure'] = size

        with open(media_json, "w") as jsonFile:
            json.dump(data, jsonFile, indent = 4)
    print("Bagging...")
    #bag = bagit.make_bag(os.getcwd(), checksums=['md5'])

def main():
    arguments = get_args()
    source = get_directory(arguments)
    json_info = get_info(source)


if __name__ == '__main__':
    main()
    exit(0)
