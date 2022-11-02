#!/usr/bin/env python3

import argparse
import os
from statistics import median
import subprocess
import bagit
import glob
import shutil
import re
import json

def get_args():
    parser = argparse.ArgumentParser(description='Copy SC Video and EM Audio to AWS')
    parser.add_argument('-d', '--directory',
                        help = 'path to directory of bags or a hard drive', required=True)
    parser.add_argument('-c', '--check_only',
                        action='store_true',
                        help = f'''check if all bags from the directory of bags/a hard drive
                        are in the AWS bucket''')
    args = parser.parse_args()
    return args

def find_bags(args):
    try:
        test_directory = os.listdir(args.directory)
    except OSError:
        exit('please retry with a valid directory of files')
    bags = []
    bag_ids = []
    if test_directory:
        path = args.directory
        all_manifests = glob.iglob(os.path.join(path,'**/manifest-md5.txt'), recursive=True)
        
        for filepath in all_manifests:
            if not '$RECYCLE' in filepath:
                bags.append(os.path.split(filepath)[0])
        for bag in bags:
            bag_id = re.findall('\d{6}', bag)[-1]
            bag_ids.append(bag_id)
    return bags, bag_ids

def get_files_and_mismatch(source_directory):
    all_file_list = []
    media_file_list = []
    json_file_list = []
    all_file_paths_list = []
    mismatch_dir = ''
    media_fn = set()
    json_fn = set()

    for root, dirs, files in os.walk(source_directory):
        for file in files: 
            item_path = os.path.join(root, file)
            pattern = r'(\w{3}_\d{6}_\w+_(sc|em))'
            if (file.lower().endswith(('sc.mp4', 'em.wav', 'em.flac')) 
            and not file.startswith('._')):
                all_file_paths_list.append(item_path)
                all_file_list.append(file)
                media_file_list.append(item_path)
                filename = re.search(pattern, file).group(1)
                media_fn.add(filename)
            if (file.lower().endswith(('sc.json', 'em.json')) and not file.startswith('._')):
                all_file_paths_list.append(item_path)
                all_file_list.append(file)
                json_file_list.append(item_path)
                filename = re.search(pattern, file).group(1)
                json_fn.add(filename)
        
        if not media_fn == json_fn:
            mismatch_dir = source_directory
            print("Mismatch of media and json: {}".format(media_fn.symmetric_difference(json_fn)))
                
    return all_file_paths_list, all_file_list, mismatch_dir, media_file_list, json_file_list

def check_bucket(filenames_list):
    to_upload = []
    for file in filenames_list:
        key_name = file.replace('flac', 'mp4').replace('wav', 'mp4')
        cmd = ['aws', 's3api', 'head-object',
           '--bucket', 'ami-carnegie-servicecopies',
           '--key', key_name]
        print(cmd)
        output = subprocess.run(cmd, capture_output=True).stdout
        if not output:
            to_upload.append(key_name)
    return to_upload

def file_type_counts(all_file_list):
    mp4_files = [ file for file in all_file_list if file.lower().endswith('.mp4')]
    wav_files = [ file for file in all_file_list if file.lower().endswith('.wav')]
    flac_files = [ file for file in all_file_list if file.lower().endswith('.flac')]
    json_files = [ file for file in all_file_list if file.lower().endswith('.json')]
    mp4_ct = len(mp4_files)
    wav_ct = len(wav_files)
    flac_ct = len(flac_files)
    json_ct = len(json_files)
    return mp4_ct, wav_ct, flac_ct, json_ct

def check_json(media_file_list, json_file_list):
    media_names = []
    json_names = []
    for file in media_file_list:
        filename = os.path.basename(file)
        media_names.append(filename)
    for file in json_file_list:
        with open(file, "r") as jsonFile:
            data = json.load(jsonFile)
            json_name = data['asset']['referenceFilename']
            json_names.append(json_name)

            if not media_names == json_names:
                print('--Check 1: Mismatch of media filenames and json asset ref filenames: {}\n'.format(set(media_names).symmetric_difference(set(json_names))))
            else:
                print('--Check 1:  Media filenames and json asset reference filenames match\n')

            barcode = data['bibliographic']['barcode']
            match = re.search(r'^33433\d+', barcode)

            if match:
                print('--Check 2: Barcodes match regex 33433+ pattern\n')
            else:
                print('--Check 2: Barcodes DO NOT match regex 33433+ pattern\n')    


def cp_files(file_list):
    for filename in sorted(file_list):
        cp_command = [
            'aws', 's3', 'cp',
            filename,
            's3://ami-carnegie-servicecopies'
            ]
        print(cp_command)
        #subprocess.call(cp_command)

def main():
    arguments = get_args()
    bags, bag_ids = find_bags(arguments)
    print(f'This directory/drive has {len(bag_ids)} bags')
    print(f'List of bags: {sorted(bag_ids)}')
    total_mp4 = total_wav = total_flac = total_json = 0
    mismatch_ls = []
    incomplete_in_bucket = []
    
    for bag in sorted(bags):
        all_file_paths, all_files, mismatch_bag, media_list, json_list = get_files_and_mismatch(bag)
        print(f'\nNow checking media and json file information for {bag}:\n')
        json_checks = check_json(media_list, json_list)
        if mismatch_bag:
            mismatch_ls.append(mismatch_bag)
        elif arguments.check_only:
            print(f'Now checking if {bag} is in the bucket:\n')
            to_upload = check_bucket(all_files)
            if to_upload:
                incomplete_in_bucket.append(bag)
                print(f'--Check 3: {bag} not in the bucket. Added to the "need to upload" list.')
            else:
                print(f'--Check 3: Yes, {bag} is in the bucket.')
        else:
            print(f'Now uploading: {bag}\n')
            mp4_ct, wav_ct, flac_ct, json_ct = file_type_counts(all_file_paths)
            cp_files(all_file_paths)
            total_mp4 += mp4_ct
            total_wav += wav_ct
            total_flac += flac_ct
            total_json += json_ct
        
    if not arguments.check_only:
        print(f'''\nThis batch uploads {total_mp4} mp4; {total_wav} wav; {total_flac} flac; and {total_json} json, except mismatched bag(s): {mismatch_ls}''')
        print(f'''\nThis upload includes {len(bag_ids) - len(mismatch_ls)} bags, except {len(mismatch_ls)} mismatched bag(s)''')
    else:
        print(f'''\nThis directory/drive has {mismatch_ls} mismatch bags. {incomplete_in_bucket} need to be uploaded to EAVie bucket.''')

if __name__ == '__main__':
    main()
    exit(0)
