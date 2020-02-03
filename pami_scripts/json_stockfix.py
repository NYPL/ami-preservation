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
    json_list = []
    for root, dirs, files in os.walk(source_directory):
        for file in files:
            if file.endswith('.json'):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                json_list.append(item_path)
    for file in json_list:
        with open(file, "r") as jsonFile:
            data = json.load(jsonFile)
            
            try:
                productID = data['source']['physicalDescription']['stockProductID']
                data['source']['physicalDescription']['stockProductID'] = str(productID)
                print(type(data['source']['physicalDescription']['stockProductID']))
            except:
                continue
        with open(file, "w") as jsonFile:
            json.dump(data, jsonFile, indent = 4)

def main():
    arguments = get_args()
    source = get_directory(arguments)
    json_info = get_info(source)


if __name__ == '__main__':
    main()
    exit(0)
