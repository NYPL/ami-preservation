#!/usr/bin/env python3

import argparse
import os
import subprocess
import bagit
import glob
import shutil

def get_args():
    parser = argparse.ArgumentParser(description='Transcode directories of video files')
    parser.add_argument('-s', '--source',
                        help = 'path to the source directory of bags', required=True)
    parser.add_argument('-d', '--destination',
                        help = 'path to the output directory', required=True)
    args = parser.parse_args()
    return args

def get_directories(args):
    try:
        test_directory = os.listdir(args.source)
    except OSError:
        exit('please retry with a valid directory of video files')

    bags = []

    if args.source:
        directory_path = os.path.abspath(args.source)
        for path in os.listdir(directory_path):
            if not path.startswith('.'):
                path = os.path.join(directory_path, path)
                if os.path.isdir(path):
                    bags.append(path)
    if os.path.exists(args.destination):
        destination_directory = os.path.abspath(args.destination)
    else:
        raise OSError("No such directory")
    return bags, destination_directory

def get_file_list(source_directory):
    file_list = []
    uncompressed_list = []
    dv_list = []

    for root, dirs, files in os.walk(source_directory):
        for file in files:
            if file.endswith('.mov'):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_list.append(item_path)

    return file_list

def transcode_files(file_list, destination_directory):
    uncompressed_list = []
    dv_list = []
    for filename in file_list:
        vidformat = subprocess.check_output(
            [
                'mediainfo', '--Language=raw',
                '--Full', "--Inform=Video;%Format%",
                filename
                ]
            ).rstrip()
        if vidformat.decode('UTF-8') == "YUV":
            uncompressed_list.append(filename)
        elif vidformat.decode('UTF-8') == "DV":
            dv_list.append(filename)
    print('V210 Count: {}'.format(len(uncompressed_list)))
    print(uncompressed_list)
    print('DV Count: {}'.format(len(dv_list)))
    print(dv_list)

    for filename in uncompressed_list:
        filenoext = os.path.splitext(filename)[0]
        output_names = "%s.mkv" % (os.path.splitext(os.path.basename(filenoext))[0])
        output_path = os.path.join(destination_directory, output_names)
        height = subprocess.check_output(
            [
                'mediainfo', '--Language=raw',
                '--Full', "--Inform=Video;%Height%",
                filename
            ]
        ).rstrip()
        ffv1_command = [
            'ffmpeg',
            '-vsync', '0',
            '-i', filename,
            '-map', '0',
            '-dn',
            '-c:v', 'ffv1',
            '-level', '3',
            '-coder', '1',
            '-context', '1',
            '-g', '1',
            '-slicecrc', '1',
            '-slices', '24',
            '-max_muxing_queue_size', '9999',
            '-c:a', 'flac',
            ]
        if height.decode('UTF-8') == '486':
            ffv1_command += [
            '-field_order', 'bt',
            '-vf', 'setfield=bff,setdar=4/3',
            '-color_primaries', 'smpte170m',
            '-color_range', 'tv',
            '-color_trc', 'bt709',
            '-colorspace', 'smpte170m',
            ]
        if height.decode('UTF-8') == '576':
            ffv1_command += [
            '-field_order', 'tb',
            '-vf', 'setfield=tff,setdar=4/3',
            '-color_primaries', 'bt470bg',
            '-color_range', 'tv',
            '-color_trc', 'bt709',
            '-colorspace', 'bt470bg',
            ]
        print(ffv1_command)
        ffv1_command += [output_path]
        subprocess.call(ffv1_command)

    for filename in dv_list:
        filenoext = os.path.splitext(filename)[0]
        output_names = "%s.dv" % (os.path.splitext(os.path.basename(filenoext))[0])
        output_path = os.path.join(destination_directory, output_names)
        dv_command = [
            'ffmpeg',
            '-i', filename,
            '-f', 'rawvideo',
            '-c:v', 'copy',
            ]
        print(dv_command)
        dv_command += [output_path]
        subprocess.call(dv_command)

def bag_transcoded_files(destination_directory, bag):
    bag_name = os.path.split(bag)[1]
    newbag_abspath = os.path.join(destination_directory, bag_name)
    pm_path = os.path.join(newbag_abspath, 'PreservationMasters')
    os.makedirs(pm_path)
    md_path = os.path.join(newbag_abspath, 'Metadata')
    os.makedirs(md_path)

    glob_abspath = os.path.abspath(os.path.join(bag, '**/*'))
    for filename in glob.glob(glob_abspath, recursive = True):
        if filename.endswith(('xlsx')):
            shutil.copy2(filename, md_path)
    mkvs = glob.iglob(os.path.join(destination_directory, '*mkv'))
    for file in mkvs:
        if os.path.isfile(file):
            shutil.move(file, pm_path)
    dvs = glob.iglob(os.path.join(destination_directory, '*dv'))
    for file in dvs:
        if os.path.isfile(file):
            shutil.move(file, pm_path)
    print("Bagging...")
    bag = bagit.make_bag(newbag_abspath, checksums=['md5'])

def main():
    arguments = get_args()
    bags, destination = get_directories(arguments)
    for bag in bags:
        print("now working on: {}".format(bag))
        list_of_files = get_file_list(bag)
        transcode_files(list_of_files, destination)
        bag_transcoded_files(destination, bag)

if __name__ == '__main__':
    main()
    exit(0)
