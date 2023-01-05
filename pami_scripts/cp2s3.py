#!/usr/bin/env python3

import argparse
import os
import subprocess
import glob
import re
import json

def get_args():
    parser = argparse.ArgumentParser(description='Copy SC Video and EM Audio to AWS')
    parser.add_argument('-d', '--directory',
                        help = '''required. A path to directory of bags or a hard drive.
                        If this is the only argument use, the script uploads service files from all bags to the AWS bucket''',
                        required=True)
    parser.add_argument('-c', '--check_only',
                        action='store_true',
                        help = f'''check if all bags from the directory of bags/a hard drive
                        are in the AWS bucket; check if there is any filename or metadata mismatch;
                        print out check result on the terminal''')
    parser.add_argument('--check_and_upload',
                        action='store_true',
                        help=f'''check if all bags from the directory of bags/a hard drive
                        are in the AWS bucket; check if there is any filename or metadata mismatch;
                        and upload ONLY the valid ones not in the AWS bucket''')
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
    em_dir = os.path.join(source_directory, 'data', 'EditMasters')
    sc_dir = os.path.join(source_directory, 'data', 'ServiceCopies')
    
    all_file_list = []
    media_paths_list = []
    json_paths_list = []
    all_file_paths_list = []
    
    if os.path.exists(em_dir) or os.path.exists(sc_dir):
        for root, dirs, files in os.walk(source_directory):
            for file in files: 
                item_path = os.path.join(root, file)  
                if (file.lower().endswith(('sc.mp4', 'em.wav', 'em.flac')) 
                    and not file.startswith('._')):
                    all_file_paths_list.append(item_path)
                    all_file_list.append(file)
                    media_paths_list.append(item_path)

                elif (file.lower().endswith(('sc.json', 'em.json')) and not file.startswith('._')):
                    all_file_paths_list.append(item_path)
                    all_file_list.append(file)
                    json_paths_list.append(item_path)
    else:
        raise OSError('No EM or SC folder')
    
    if not all_file_paths_list:
        raise FileNotFoundError('No files in the EM or SC folder')

    return all_file_paths_list, all_file_list, media_paths_list, json_paths_list

def valid_fn_convention(all_file_list):
    pattern = r'(\w{3}_\d{6}_\w+_(sc|em))'
    invalid_fn_ls = []

    for file in all_file_list:
        try:
            re.search(pattern, file).group(0)
            return True
        except AttributeError:
            print(f'{file} not named correctly')
            invalid_fn_ls.append(file)
            return invalid_fn_ls

def valid_media_json_match(media_paths_list, json_paths_list):
    media_set = set([os.path.splitext(os.path.basename(i))[0]for i in media_paths_list])
    json_set = set([os.path.splitext(os.path.basename(i))[0] for i in json_paths_list])
    
    if media_set == json_set:
        return True
    else:
        return media_set.symmetric_difference(json_set)

def valid_json_reference(media_file_list, json_file_list):
    media_names = [os.path.basename(file) for file in media_file_list]
    json_names = []
    
    for file in json_file_list:
        with open(file, "r", encoding='utf-8-sig') as jsonFile:
            data = json.load(jsonFile)
            json_name = data['asset']['referenceFilename']
            json_names.append(json_name)
    if media_names == json_names:
        return True
    else:
        return json_names

def valid_json_barcode(json_file_list):
    for file in json_file_list:
        with open(file, "r", encoding='utf-8-sig') as jsonFile:
            data = json.load(jsonFile)
            barcode = data['bibliographic']['barcode']
            match = re.search(r'^33433\d+', barcode)

            if match:
                return True
            else:
                return file

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
            output_json_mp4 = subprocess.run(cmd, capture_output=True).stdout
            if not output_json_mp4:
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
    invalid_fn_ls = []
    fn_mismatch_ls = []
    json_mismatch_ls = []
    bc_mismatch_ls = []
    incomplete_in_bucket = []
    
    for bag in sorted(bags):
        all_file_paths, all_files, media_list, json_list = get_files(bag)
        fn = valid_fn_convention(all_files)
        media_json = valid_media_json_match(media_list, json_list)
        reference = valid_json_reference(media_list, json_list)
        barcode = valid_json_barcode(json_list)
        
        if (fn == True and media_json == True and reference == True and barcode == True):
            if arguments.check_only or arguments.check_and_upload:
                print(f'Now checking if {bag} is in the bucket:\n')
                to_upload = check_bucket(all_files)
                if to_upload:
                    incomplete_in_bucket.append(bag)
                    print(f'\nNo, {bag} not in the bucket.')
                    if arguments.check_and_upload:
                        print(f'Now uploading: {bag}\n')
                        mp4_ct, wav_ct, flac_ct, json_ct = file_type_counts(all_file_paths)
                        cp_files(all_file_paths)
                        total_mp4 += mp4_ct
                        total_wav += wav_ct
                        total_flac += flac_ct
                        total_json += json_ct
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
        else:
            if fn != True:
                invalid_fn_ls.append(fn)
            if media_json != True:
                fn_mismatch_ls.append(media_json)
            if reference != True:
                json_mismatch_ls.append(reference)
            if barcode != True:
                bc_mismatch_ls.append(barcode)
 
    if arguments.check_only:
        print(f'''\nThis directory/drive has bags with invalid filename(s): {invalid_fn_ls}
        media and json mismatched bag(s): {fn_mismatch_ls} and
        json reference mismatched bag(s): {json_mismatch_ls} and
        barcode mismatched bag(s): {bc_mismatch_ls}.
        {incomplete_in_bucket} need to be uploaded to EAVie bucket.''')
    
    elif arguments.check_and_upload:
        print(f'''\nThis batch uploads {total_mp4} mp4; {total_wav} wav; {total_flac} flac; and {total_json} json,
        except:
        bags with invalid filename(s): {invalid_fn_ls}
        media and json mismatched bag(s): {fn_mismatch_ls} and
        json reference mismatched bag(s): {json_mismatch_ls} and
        barcode mismatched bag(s): {bc_mismatch_ls}.''')

    else:
        print(f'''\nThis batch uploads {total_mp4} mp4; {total_wav} wav; {total_flac} flac; and {total_json} json,
        except:
        bags with invalid filename(s): {invalid_fn_ls}
        media and json mismatched bag(s): {fn_mismatch_ls} and
        json reference mismatched bag(s): {json_mismatch_ls} and
        barcode mismatched bag(s): {bc_mismatch_ls}.''')

if __name__ == '__main__':
    main()
    exit(0)
