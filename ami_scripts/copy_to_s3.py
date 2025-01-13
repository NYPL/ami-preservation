#!/usr/bin/env python3

import argparse
import os
import subprocess
import glob
import re
import json
import warnings

def get_args():
    parser = argparse.ArgumentParser(description='Copy SC Video and EM Audio to AWS')

    # CHANGED: allow multiple directories for -d/--directory
    parser.add_argument(
        '-d', '--directories',
        nargs='+',
        required=True,
        help=('One or more bag directories to be processed. '
              'E.g.:  -d /path/to/MDR0001364 /path/to/MDR0001348')
    )

    parser.add_argument(
        '-c', '--check_only',
        action='store_true',
        help=('Check if all bags from the directory(s) are in the AWS bucket; '
              'check if there is any filename or metadata mismatch; '
              'print out check result on the terminal')
    )
    parser.add_argument(
        '--check_and_upload',
        action='store_true',
        help=('Check if all bags from the directory(s) are in the AWS bucket; '
              'check if there is any filename or metadata mismatch; '
              'and upload ONLY the valid ones not in the AWS bucket')
    )
    args = parser.parse_args()
    return args

def find_bags(directory):
    """
    Given a single directory path, finds all bagit bag folders
    by locating 'manifest-md5.txt' recursively.
    Returns two lists: list_of_bag_paths, list_of_bag_ids
    """
    try:
        test_directory = os.listdir(directory)
    except OSError:
        exit(f'Please retry with a valid directory of files: {directory}')

    bags = []
    bag_ids = []
    if test_directory:
        all_manifests = glob.iglob(
            os.path.join(directory, '**', 'manifest-md5.txt'),
            recursive=True
        )
        for filepath in all_manifests:
            if '$RECYCLE' not in filepath:  # skip recycle bin
                bag_path = os.path.split(filepath)[0]
                bags.append(bag_path)

        for bag in bags:
            # In your original example: re.findall('\d{6}', bag)[-1] 
            # might cause an IndexError if the path doesn't match.
            # We'll do a small try/except or just check length.
            match = re.findall(r'\d{6}', bag)
            if match:
                bag_ids.append(match[-1])
            else:
                bag_ids.append('UnknownBagID')
    return bags, bag_ids

def get_files(source_directory):
    """
    Returns a tuple of:
      all_file_paths_list,
      all_file_list (filenames only),
      media_paths_list,
      json_paths_list
    """
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

                elif (file.lower().endswith(('sc.json', 'em.json'))
                      and not file.startswith('._')):
                    all_file_paths_list.append(item_path)
                    all_file_list.append(file)
                    json_paths_list.append(item_path)
    else:
        warnings.warn(f'{source_directory} has no EM or SC folder')

    if not all_file_paths_list:
        warnings.warn('No files found in the EM or SC folder')

    return all_file_paths_list, all_file_list, media_paths_list, json_paths_list

def valid_fn_convention(all_file_list):
    """
    Check that filenames match pattern: \w{3}_\d{6}_\w+_(sc|em)
    Returns True if valid, else returns a list of invalid filenames.
    """
    pattern = r'(\w{3}_\d{6}_\w+_(sc|em))'
    invalid_fn_ls = []

    for file in all_file_list:
        try:
            _ = re.search(pattern, file).group(0)
        except AttributeError:
            print(f'{file} not named correctly')
            invalid_fn_ls.append(file)
    # If there were any invalid filenames, return them
    if invalid_fn_ls:
        return invalid_fn_ls
    return True

def valid_media_json_match(media_paths_list, json_paths_list):
    """
    Checks that for every media file there is a matching JSON file 
    (base name should match).
    Returns True if perfect match, else returns the difference.
    """
    media_set = set([os.path.splitext(os.path.basename(i))[0]
                     for i in media_paths_list])
    json_set = set([os.path.splitext(os.path.basename(i))[0]
                    for i in json_paths_list])

    if media_set == json_set:
        return True
    else:
        return media_set.symmetric_difference(json_set)

def valid_json_reference(media_file_list, json_file_list):
    """
    Checks the 'asset.referenceFilename' in each JSON 
    to ensure it matches the actual media filename.
    Returns True if all match, otherwise returns a set of mismatches.
    """
    media_names = set([os.path.basename(file) for file in media_file_list])
    json_names = set()

    for file in json_file_list:
        with open(file, "r", encoding='utf-8-sig') as jsonFile:
            data = json.load(jsonFile)
            json_name = data['asset']['referenceFilename']
            json_names.add(json_name)
    if media_names == json_names:
        return True
    else:
        return json_names.symmetric_difference(media_names)

def valid_json_barcode(json_file_list):
    """
    Checks that each JSON's 'bibliographic.barcode' starts with '33433...'.
    If all good, return True. Else return the first problematic file.
    """
    for file in json_file_list:
        with open(file, "r", encoding='utf-8-sig') as jsonFile:
            data = json.load(jsonFile)
            barcode = data['bibliographic']['barcode']
            match = re.search(r'^33433\d+', barcode)
            if not match:
                return file
    return True

def check_bucket(filenames_list):
    """
    Checks if the given filenames exist in the bucket by calling `aws s3api head-object`.
    If an audio file is not found, we also check if its SC version is there, etc.
    Returns a list of files that need to be uploaded.
    """
    to_upload = []
    cmd = ['aws', 's3api', 'head-object',
           '--bucket', 'ami-carnegie-servicecopies',
           '--key', '']
    for file in filenames_list:
        if 'flac' in file or 'wav' in file:
            cmd[-1] = file
            output_original_media = subprocess.run(cmd, capture_output=True).stdout
            if not output_original_media:
                mp4_key = file.replace('flac', 'mp4').replace('wav', 'mp4')
                cmd[-1] = mp4_key
                output_mp4 = subprocess.run(cmd, capture_output=True).stdout
                if not output_mp4:
                    to_upload.append(file)
        else:
            cmd[-1] = file
            output_json_mp4 = subprocess.run(cmd, capture_output=True).stdout
            if not output_json_mp4:
                to_upload.append(file)
    return to_upload

def file_type_counts(all_file_list):
    """
    Returns counts of how many mp4, wav, flac, json are in the list.
    """
    mp4_files = [f for f in all_file_list if f.lower().endswith('.mp4')]
    wav_files = [f for f in all_file_list if f.lower().endswith('.wav')]
    flac_files = [f for f in all_file_list if f.lower().endswith('.flac')]
    json_files = [f for f in all_file_list if f.lower().endswith('.json')]
    mp4_ct = len(mp4_files)
    wav_ct = len(wav_files)
    flac_ct = len(flac_files)
    json_ct = len(json_files)
    return mp4_ct, wav_ct, flac_ct, json_ct

def cp_files(file_list):
    """
    Uploads the given files to S3 via `aws s3 cp`.
    """
    for filename in sorted(file_list):
        cp_command = [
            'aws', 's3', 'cp',
            filename,
            's3://ami-carnegie-servicecopies'
        ]
        print(cp_command)
        subprocess.call(cp_command)

def process_single_directory(directory, arguments):
    """
    Process a SINGLE directory of bagit bags: 
      - find all bags
      - do all checks
      - if necessary, upload 
    Returns a dictionary with summary info that we can print later.
    """
    bags, bag_ids = find_bags(directory)

    summary = {
        'directory': directory,
        'num_bags_found': len(bag_ids),
        'bag_ids': sorted(bag_ids),
        'em_sc_issue_bags': [],
        'invalid_fn_ls': [],
        'fn_mismatch_ls': [],
        'json_mismatch_ls': [],
        'bc_mismatch_ls': [],
        'incomplete_in_bucket': [],
        'uploaded_counts': {
            'mp4': 0,
            'wav': 0,
            'flac': 0,
            'json': 0
        }
    }

    for bag in sorted(bags):
        all_file_paths, all_files, media_list, json_list = get_files(bag)
        if not all_file_paths:
            summary['em_sc_issue_bags'].append(bag)
        else:
            fn_check = valid_fn_convention(all_files)
            media_json_check = valid_media_json_match(media_list, json_list)
            reference_check = valid_json_reference(media_list, json_list)
            barcode_check = valid_json_barcode(json_list)

            if (fn_check == True and
                media_json_check == True and
                reference_check == True and
                barcode_check == True):
                
                # If we're only checking or checking+uploading:
                if arguments.check_only or arguments.check_and_upload:
                    print(f'Now checking if {bag} is in the bucket:\n')
                    to_upload = check_bucket(all_files)
                    if to_upload:
                        summary['incomplete_in_bucket'].append(bag)
                        print(f'\nNo, {bag} not in the bucket.')
                        if arguments.check_and_upload:
                            print(f'Now uploading: {bag}\n')
                            mp4_ct, wav_ct, flac_ct, json_ct = file_type_counts(all_file_paths)
                            cp_files(all_file_paths)
                            summary['uploaded_counts']['mp4'] += mp4_ct
                            summary['uploaded_counts']['wav'] += wav_ct
                            summary['uploaded_counts']['flac'] += flac_ct
                            summary['uploaded_counts']['json'] += json_ct
                    else:
                        print(f'\nYes, {bag} is in the bucket.')
                else:
                    # No checks, just upload
                    print(f'Now uploading: {bag}\n')
                    mp4_ct, wav_ct, flac_ct, json_ct = file_type_counts(all_file_paths)
                    cp_files(all_file_paths)
                    summary['uploaded_counts']['mp4'] += mp4_ct
                    summary['uploaded_counts']['wav'] += wav_ct
                    summary['uploaded_counts']['flac'] += flac_ct
                    summary['uploaded_counts']['json'] += json_ct

            else:
                # Something didn't check out
                if fn_check != True:
                    # fn_check is a list of invalid filenames if not True
                    summary['invalid_fn_ls'].extend(fn_check)
                if media_json_check != True:
                    summary['fn_mismatch_ls'].append(media_json_check)
                if reference_check != True:
                    summary['json_mismatch_ls'].append(reference_check)
                if barcode_check != True:
                    summary['bc_mismatch_ls'].append(barcode_check)

    return summary

def print_summary(arguments, summary):
    """
    Print summary info for a single directory after it's been processed.
    The summary here is a dictionary returned by `process_single_directory`.
    """
    directory = summary['directory']
    print(f"\n=== Summary for {directory} ===")
    print(f"Found {summary['num_bags_found']} bags.")
    print(f"Bag IDs: {summary['bag_ids']}")
    
    if arguments.check_only:
        print(f"""
EM or SC issue bags: {summary['em_sc_issue_bags']}
Bags with invalid filename(s): {summary['invalid_fn_ls']}
Media/JSON mismatched bag(s): {summary['fn_mismatch_ls']}
JSON reference mismatched bag(s): {summary['json_mismatch_ls']}
Barcode mismatched bag(s): {summary['bc_mismatch_ls']}
Bags needing upload: {summary['incomplete_in_bucket']}
        """)
    elif arguments.check_and_upload:
        uc = summary['uploaded_counts']
        print(f"""
Uploaded counts: {uc['mp4']} MP4, {uc['wav']} WAV, {uc['flac']} FLAC, {uc['json']} JSON

EM or SC issue bags: {summary['em_sc_issue_bags']}
Bags with invalid filename(s): {summary['invalid_fn_ls']}
Media/JSON mismatched bag(s): {summary['fn_mismatch_ls']}
JSON reference mismatched bag(s): {summary['json_mismatch_ls']}
Barcode mismatched bag(s): {summary['bc_mismatch_ls']}
        """)
    else:
        uc = summary['uploaded_counts']
        print(f"""
Uploaded counts: {uc['mp4']} MP4, {uc['wav']} WAV, {uc['flac']} FLAC, {uc['json']} JSON

EM or SC issue bags: {summary['em_sc_issue_bags']}
Bags with invalid filename(s): {summary['invalid_fn_ls']}
Media/JSON mismatched bag(s): {summary['fn_mismatch_ls']}
JSON reference mismatched bag(s): {summary['json_mismatch_ls']}
Barcode mismatched bag(s): {summary['bc_mismatch_ls']}
        """)

def main():
    arguments = get_args()

    # Process each directory individually and store results
    all_summaries = []
    for directory in arguments.directories:
        print(f"\nProcessing directory: {directory}")
        summary = process_single_directory(directory, arguments)
        all_summaries.append(summary)
    
    # Print a final summary for each directory
    for summary in all_summaries:
        print_summary(arguments, summary)

if __name__ == '__main__':
    main()
    exit(0)