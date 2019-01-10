#!/usr/bin/env python3

import argparse
import os
import subprocess
import bagit
import glob
import shutil

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
        exit('please retry with a valid directory of video files')
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
            if file.endswith('.mov'):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_list.append(item_path)
    print(file_list)
    for filename in file_list:
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
            '-c:a', 'copy',
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
    return file_list

def bag_mkvs(source_directory, destination_directory):
    os.chdir(destination_directory)
    src_name = os.path.split(source_directory)[1]
    os.mkdir(src_name)
    os.chdir(src_name)
    path = 'PreservationMasters'
    path2 = 'Metadata'
    os.mkdir(path)
    os.mkdir(path2)
    glob_abspath = os.path.abspath(os.path.join(source_directory, '**/*'))
    for filename in glob.glob(glob_abspath, recursive = True):
        if filename.endswith(('xlsx')):
            shutil.copy2(filename, path2)
    files = glob.iglob(os.path.join(destination_directory, '*mkv'))
    for file in files:
        if os.path.isfile(file):
            shutil.move(file, path)
    print("Bagging...")
    bag = bagit.make_bag(os.getcwd(), checksums=['md5'])

def main():
    arguments = get_args()
    source, destination = get_directory(arguments)
    list_of_files = get_file_list(source, destination)
    bags = bag_mkvs(source, destination)

if __name__ == '__main__':
    main()
    exit(0)
