#!/usr/bin/env python3

import argparse
import os
import subprocess
import bagit
import glob
import shutil
import re

def get_args():
    parser = argparse.ArgumentParser(description='Copy SC Video and EM Audio to AWS')
    parser.add_argument('-d', '--directory',
                        help = 'path to directory of bags or a hard drive', required=True)
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
            bags.append(os.path.split(filepath)[0])
        for bag in bags:
            bag_id = re.findall('\d{6}', bag)[-1]
            bag_ids.append(bag_id)
    return bags, bag_ids

def check_media_json_match(source_directory):
    media_fn = set()
    json_fn = set()
    for root, dirs, files in os.walk(source_directory): 
        for file in files:
            pattern = r'(\w{3}_\d{6}_\w+_(sc|em))'
            if (file.lower().endswith(('sc.mp4', 'em.wav', 'em.flac')) 
            and not file.startswith('._')):
                filename = re.search(pattern, file).group(1)
                media_fn.add(filename)
            if (file.lower().endswith(('sc.json', 'em.json')) and not file.startswith('._')):
                filename = re.search(pattern, file).group(1)
                json_fn.add(filename)
        if not media_fn == json_fn:
            print("Mismatch of media and json: {}".format(media_fn.symmetric_difference(json_fn)))
        return True

def get_file_list(source_directory):
    all_file_list = []
    for root, dirs, files in os.walk(source_directory):        
        for file in files:    
            item_path = os.path.join(root, file)
            if (file.lower().endswith(('sc.mp4', 'sc.json', 'em.wav', 'em.flac', 'em.json')) 
            and not file.startswith('._')):
                all_file_list.append(item_path)
    return all_file_list

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
    print(f'This directory/drive has {len(bag_ids)} bags.')
    print(f'This is the list of bags: {bag_ids}.')
    for bag in bags:
        print("now working on: {}".format(bag))
        good_bag = check_media_json_match(bag)
        if good_bag == True:
            list_of_files = get_file_list(bag)
            cp_files(list_of_files)

if __name__ == '__main__':
    main()
    exit(0)
