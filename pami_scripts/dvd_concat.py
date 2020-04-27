#!/usr/bin/env python3

import argparse
import os
import subprocess
import bagit
import glob
import shutil

def get_args():
    parser = argparse.ArgumentParser(description='Concat and Transcode a directory of DVD-produced MKV to MP4 files')
    parser.add_argument('-s', '--source',
                        help = 'path to directory of source DVD files', required=True)
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
            item_path = os.path.join(root, file)
            filename = os.path.basename(item_path)
            file_list.append(filename)
    print(file_list)
    os.chdir(source_directory)
    with open('mylist.txt', 'w') as f:
        for item in sorted(file_list):
            f.write("file '{}'\n".format(item))

    concat_name = os.path.splitext(file_list[0])[0]
    fixed_name = concat_name.rsplit('_', 1)[0]

    output_name = "mym_%s_v01_sc.mp4" % (fixed_name)
    output_path = os.path.join(destination_directory, output_name)

    print(output_name)
    concat_command = [
        'ffmpeg',
        '-f', 'concat',
        '-i', 'mylist.txt',
        '-map', '0:a',
        '-map', '0:v',
        '-c:v', 'libx264',
        '-movflags', 'faststart',
        '-pix_fmt', 'yuv420p',
        '-b:v', '3500000',
        '-bufsize', '1750000',
        '-maxrate', '3500000',
        '-vf', 'yadif',
        '-c:a', 'aac',
        '-strict',
        '-2',
        '-b:a', '320000',
        '-ar', '48000',
        ]
    print(concat_command)
    concat_command += [output_path]
    subprocess.call(concat_command)
    return file_list

def main():
    arguments = get_args()
    source, destination = get_directory(arguments)
    list_of_files = get_file_list(source, destination)

if __name__ == '__main__':
    main()
    exit(0)
