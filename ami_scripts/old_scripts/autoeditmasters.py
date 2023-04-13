#!/usr/bin/env python3

import argparse
import os
import subprocess
import bagit
import glob
import shutil
import json

def get_args():
    parser = argparse.ArgumentParser(description='Automated edit master files: trimming heads/tails, volume normal')
    parser.add_argument('-s', '--source',
                        help = 'path to the directory of audio files', required=True)
    parser.add_argument('--denoise', action='store_true',
                        help = 'add optional FFmpeg arnndn filter for noise reduction')
    args = parser.parse_args()
    return args

def get_directory(args):
    try:
        test_directory = os.listdir(args.source)
    except OSError:
        exit('please retry with a valid directory of audio files')
    source_directory = args.source

    return source_directory

def get_file_list(source_directory, args):
    file_list = []
    for root, dirs, files in os.walk(source_directory):
        for file in files:
            if file.endswith(('.wav', 'flac')):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_list.append(item_path)

    edit_path = source_directory.replace('PreservationMasters', 'EditMasters')
    if not os.path.exists(edit_path):
        os.makedirs(edit_path)

    return file_list, edit_path

def trim(file_list, edit_path):
    for file in sorted(file_list):
        filenoext, ext = os.path.splitext(file)
        output_names = os.path.splitext(os.path.basename(filenoext))[0].replace('_pm', '_temp') + ext
        output_path = os.path.join(edit_path, output_names)

        trim_command = [
            'ffmpeg',
            '-i', file,
            '-af', 'silenceremove=start_threshold=-65dB:start_duration=1:start_periods=1,areverse,silenceremove=start_threshold=-65dB:start_duration=1:start_periods=1,areverse',
            ]

        if file.endswith('wav'):
            trim_command += [
                '-f', 'wav',
                '-rf64', 'auto',
                '-c:a', 'pcm_s24le',
                '-ar', '96k'
                ]
        elif file.endswith('flac'):
            trim_command += [
                '-c:a', 'flac',
                '-ar', '96k'
                ]

        print(trim_command)
        trim_command += [output_path]
        subprocess.call(trim_command)

def loudnorm(file_list, edit_path):
    edit_list = []
    for root, dirs, files in os.walk(edit_path):
        for file in files:
            if file.endswith(('.wav', '.flac')):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                edit_list.append(item_path)

    for file in sorted(edit_list):
        filenoext, ext = os.path.splitext(file)
        output_names = os.path.splitext(os.path.basename(filenoext))[0].replace('_temp', '_em') + ext
        output_path = os.path.join(edit_path, output_names)

        target_il = '-20.0'
        target_lra = '+7.0'
        target_tp = '-2.0'

        loudnorm_1stpass = [
            'ffmpeg',
            '-i', file,
            '-af', 'loudnorm=dual_mono=true:I={}:LRA={}:tp={}:print_format=json'.format(target_il, target_lra, target_tp),
            '-f', 'null',
            '-'
            ]
        pipe = subprocess.run(loudnorm_1stpass,
                       stderr=subprocess.PIPE,
                       universal_newlines=True)
        lines = pipe.stderr.splitlines()
        loudlines = ''.join(lines[-12:])
        stats = json.loads(loudlines)

        loudnorm_2ndpass = [
            'ffmpeg',
            '-i', file,
            '-af', 'loudnorm=dual_mono=true:print_format=summary:linear=true:I={}:LRA={}:tp={}:measured_I={}:measured_LRA={}:measured_tp={}:measured_thresh={}:offset={}'.format(target_il, target_lra, target_tp, stats['input_i'],stats['input_lra'],stats['input_tp'],stats['input_thresh'],stats['target_offset']),
            ]
        if file.endswith('wav'):
            loudnorm_2ndpass += [
                '-f', 'wav',
                '-rf64', 'auto',
                '-c:a', 'pcm_s24le',
                '-ar', '96k'
                ]
        elif file.endswith('flac'):
            loudnorm_2ndpass += [
                '-c:a', 'flac',
                '-ar', '96k'
                ]
        print(loudnorm_2ndpass)
        loudnorm_2ndpass += [output_path]
        subprocess.call(loudnorm_2ndpass)
        os.remove(file)

def denoise(file_list, edit_path, args):
    if args.denoise:
        dn_list = []
        for root, dirs, files in os.walk(edit_path):
            for file in files:
                if file.endswith(('.wav', '.flac')):
                    item_path = os.path.join(root, file)
                    filename = os.path.basename(item_path)
                    dn_list.append(item_path)

        for file in sorted(dn_list):
            filenoext, ext = os.path.splitext(file)
            output_names = os.path.splitext(os.path.basename(filenoext))[0].replace('_em', '_denoise') + ext
            output_path = os.path.join(edit_path, output_names)

            dn_command = [
                'ffmpeg',
                '-i', file,
                '-af', 'arnndn=m=./arnndn-models/bd.rnnn',
                ]

            if file.endswith('wav'):
                dn_command += [
                   '-f', 'wav',
                   '-rf64', 'auto',
                   '-c:a', 'pcm_s24le',
                   '-ar', '96k'
                   ]
            elif file.endswith('flac'):
                dn_command += [
                    '-c:a', 'flac',
                    '-ar', '96k'
                    ]

            print(dn_command)
            dn_command += [output_path]
            subprocess.call(dn_command)
            os.remove(file)

def main():
    arguments = get_args()
    source = get_directory(arguments)
    file_list, edit_path = get_file_list(source, arguments)
    trim(file_list, edit_path)
    loudnorm(file_list, edit_path)
    denoise(file_list, edit_path, arguments)

if __name__ == '__main__':
    main()
    exit(0)
