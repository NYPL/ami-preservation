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

def get_files(source_directory):
    all_file_list = []
    media_file_list = []
    json_file_list = []
    all_file_paths_list = []

    for root, dirs, files in os.walk(source_directory):
        for file in files: 
            item_path = os.path.join(root, file)  
            if (file.lower().endswith(('sc.mp4', 'em.wav', 'em.flac')) 
                and not file.startswith('._')):
                all_file_paths_list.append(item_path)
                all_file_list.append(file)
                media_file_list.append(item_path)

            elif (file.lower().endswith(('sc.json', 'em.json')) and not file.startswith('._')):
                all_file_paths_list.append(item_path)
                all_file_list.append(file)
                json_file_list.append(item_path)
            
    return all_file_paths_list, all_file_list, media_file_list, json_file_list

def check_fn_convention(all_file_list):
    pattern = r'(\w{3}_\d{6}_\w+_(sc|em))'
    answer = bool
    for file in all_file_list:
        try:
            re.search(pattern, file).group(0)
            answer = True
        except AttributeError:
            print(f'{file} not named correctly')
            answer = False
            continue
    return answer

def check_bucket(filenames_list):
    to_upload = []
    cmd = ['aws', 's3api', 'head-object',
            '--bucket', 'ami-carnegie-servicecopies',
            '--key', '']
    for file in filenames_list:
        if 'flac' in file or 'wav' in file:
            cmd[-1] = file
            print(cmd)
            output_original_media = subprocess.run(cmd, capture_output=True).stdout
            if not output_original_media:
                mp4_key = file.replace('flac', 'mp4').replace('wav', 'mp4')
                cmd[-1] = mp4_key
                print(cmd)
                output_mp4 = subprocess.run(cmd, capture_output=True).stdout
                if not output_mp4:
                    to_upload.append(file)
        else:
            cmd[-1] = file
            print(cmd)
            output_json = subprocess.run(cmd, capture_output=True).stdout
            if not output_json:
                to_upload.append(file)
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
    fn_mismatch = ''
    barcode_mismatch = ''
    
    for file in media_file_list:
        filename = os.path.basename(file)
        media_names.append(filename)
    for file in json_file_list:
        with open(file, "r") as jsonFile:
            data = json.load(jsonFile)
            json_name = data['asset']['referenceFilename']
            json_names.append(json_name)

            if not media_names == json_names:
                fn_mismatch = file
            else:
                pass

            barcode = data['bibliographic']['barcode']
            match = re.search(r'^33433\d+', barcode)

            if match:
                pass
            else:
                barcode_mismatch = file
                
    
    return fn_mismatch, barcode_mismatch


def cp_files(file_list):
    for filename in sorted(file_list):
        cp_command = [
            'aws', 's3', 'cp',
            filename,
            's3://ami-carnegie-servicecopies'
            ]
        print(cp_command)
        subprocess.call(cp_command)

def main():
    arguments = get_args()
    bags, bag_ids = find_bags(arguments)
    print(f'This directory/drive has {len(bag_ids)} bags')
    print(f'List of bags: {sorted(bag_ids)}')
    total_mp4 = total_wav = total_flac = total_json = 0
    fn_mismatch_ls = []
    bc_mismatch_ls = []
    incomplete_in_bucket = []
    incorrect_name_ls = []
    
    for bag in sorted(bags):
        all_file_paths, all_files, media_list, json_list = get_files(bag)
        fn_mismatch, barcode_mismatch = check_json(media_list, json_list)
        fn_bool = check_fn_convention(all_files)
        
        if fn_mismatch:
            fn_mismatch_ls.append(fn_mismatch)

        elif barcode_mismatch:
            bc_mismatch_ls.append(barcode_mismatch)
        
        elif fn_bool == False:
            incorrect_name_ls.append(bag)

        elif arguments.check_only:
            print(f'Now checking if {bag} is in the bucket:\n')
            to_upload = check_bucket(all_files)
            if to_upload:
                incomplete_in_bucket.append(bag)
                print(f'\nNo, {bag} not in the bucket. Added to the "need to upload" list.')
            else:
                print(f'\nYes, {bag} is in the bucket.')
        else:
            print(f'Now uploading: {bag}\n')
            mp4_ct, wav_ct, flac_ct, json_ct = file_type_counts(all_file_paths)
            cp_files(all_file_paths)
            total_mp4 += mp4_ct
            total_wav += wav_ct
            total_flac += flac_ct
            total_json += json_ct
        
    if not arguments.check_only:
        print(f'''\nThis batch uploads {total_mp4} mp4; {total_wav} wav; {total_flac} flac; and {total_json} json,
        except filename mismatched bag(s): {fn_mismatch_ls} and
        barcode mismatched bag(s): {bc_mismatch_ls} and
        incorrect file names bag(s): {incorrect_name_ls}''')
      
    else:
        print(f'''\nThis directory/drive has filename mismatched bag(s): {fn_mismatch_ls} and
        barcode mismatched bag(s): {bc_mismatch_ls} and incorrect file names bag(s): {incorrect_name_ls}.
        {incomplete_in_bucket} need to be uploaded to EAVie bucket.''')

if __name__ == '__main__':
    main()
    exit(0)
