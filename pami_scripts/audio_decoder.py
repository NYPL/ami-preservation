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
    parser.add_argument('-d', '--destination',
                        help = 'path to the output directory', required=True)
    args = parser.parse_args()
    return args

def get_directory(args):
    try:
        test_directory = os.listdir(args.source)
    except OSError:
        exit('please retry with a valid directory of audio files')
    source_directory = args.source
    if os.path.exists(args.destination):
        destination_directory = os.path.abspath(args.destination)
    else:
        raise OSError("No such directory")
    return source_directory, destination_directory

def get_file_list(source_directory, destination_directory):
    file_list = []
    for root, dirs, files in os.walk(source_directory):
        for file in files:
            if file.endswith('.flac'):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_list.append(item_path)
    print(file_list)
    for filename in file_list:
        filenoext = os.path.splitext(filename)[0]
        output_names = "%s.wav" % (os.path.splitext(os.path.basename(filenoext))[0])
        output_path = os.path.join(destination_directory, output_names)
        flac_command = [
            'flac', filename,
            '--decode',
            '--keep-foreign-metadata',
            '--preserve-modtime',
            '--verify',
            '-o'
            ]
        print(flac_command)
        flac_command += [output_path]
        subprocess.call(flac_command)
    return file_list

def org_flacs(source_directory, destination_directory):
    os.chdir(destination_directory)
    src_name = os.path.split(source_directory)[1]
    os.mkdir(src_name)
    os.chdir(src_name)
    path = 'PreservationMasters'
    path2 = 'EditMasters'
    os.mkdir(path)
    os.mkdir(path2)
    PM_files = glob.iglob(os.path.join(destination_directory, '*pm.wav'))
    for file in PM_files:
        if os.path.isfile(file):
            shutil.move(file, path)
    EM_files = glob.iglob(os.path.join(destination_directory, '*em.wav'))
    for file in EM_files:
        if os.path.isfile(file):
            shutil.move(file, path2)
    glob_abspath = os.path.abspath(os.path.join(source_directory, '**/*'))
    for filename in glob.glob(glob_abspath, recursive = True):
        if filename.endswith(('em.json')):
            shutil.copy2(filename, path2)
        if filename.endswith(('pm.json')):
            shutil.copy2(filename, path)

def get_flac_info(destination_directory):
    flac_dir = os.getcwd()
    os.chdir(flac_dir)
    file_list = []
    for root, dirs, files in os.walk(flac_dir):
        for file in files:
            if file.endswith('.wav'):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_list.append(item_path)
            if file.endswith('.json'):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_list.append(item_path)
    for filename in file_list:
        print(filename)
        if filename.endswith('.wav'):
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
            flac_format = subprocess.check_output(
                [
                    'mediainfo', '--Language=raw',
                    '--Full', "--Inform=General;%Format%",
                    filename
                ]
                ).rstrip()
            flac_format = flac_format.decode('UTF-8')
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
        if filename.endswith('.json'):
            print(filename)
            with open(filename, "r") as jsonFile:
                data = json.load(jsonFile)

            data['asset']['referenceFilename'] = name
            data['technical']['filename'] = technicalFilename
            data['technical']['extension'] = extension
            data['technical']['dateCreated'] = date
            data['technical']['fileFormat'] = flac_format
            data['technical']['audioCodec'] = codec
            data['technical']['fileSize']['measure'] = size

            with open(filename, "w") as jsonFile:
                json.dump(data, jsonFile, indent = 4)

    #bag = bagit.make_bag(os.getcwd(), checksums=['md5'])

def main():
    arguments = get_args()
    source, destination = get_directory(arguments)
    list_of_files = get_file_list(source, destination)
    bags = org_flacs(source, destination)
    json_info = get_flac_info(destination)

if __name__ == '__main__':
    main()
    exit(0)
