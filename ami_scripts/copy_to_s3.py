#!/usr/bin/env python3

import argparse
import os
import subprocess
import glob
import re
import json
import warnings
import tempfile
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound, TokenRetrievalError, SSOTokenLoadError
except ImportError:
    print("\n[ERROR] Required library 'boto3' is not installed.")
    print("Please install it by running:")
    print("    python3 -m pip install boto3")
    print("Or if using a virtual environment, ensure it is activated.\n")
    sys.exit(1)

BUCKET_NAME = 'ami-carnegie-servicecopies'

def get_args():
    parser = argparse.ArgumentParser(description='Copy SC Video and EM Audio to AWS')

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
    
    parser.add_argument(
        '-p', '--profile',
        help='The AWS profile name to use (for SSO login)',
        default=None
    )

    parser.add_argument(
        '--transcode',
        action='store_true',
        help=('If set, transcode FLAC files to MP4 (AAC) in a temporary directory '
              'and update corresponding JSON referenceFilename before uploading. '
              'Original source files remain unchanged.')
    )

    parser.add_argument(
        '--dry_run',
        action='store_true',
        help=('Simulate the process without running FFmpeg commands, modifying JSONs, '
              'or uploading to AWS. Useful for verifying logic.')
    )
    
    args = parser.parse_args()
    return args

def get_s3_client(profile_name=None):
    """
    Establish an S3 client session.
    Checks for valid credentials immediately.
    """
    try:
        session = boto3.Session(profile_name=profile_name)
        # Capture the actual profile being used (handles default/env vars)
        effective_profile = session.profile_name 
        
        sts = session.client('sts')
        # Simple call to verify credentials are active
        identity = sts.get_caller_identity()
        # print(f"Authenticated as: {identity['Arn']}")
        return session.client('s3')
    except (NoCredentialsError, ClientError, ProfileNotFound, TokenRetrievalError, SSOTokenLoadError) as e:
        print(f"\n[ERROR] AWS Authentication Failed: {e}")
        print("Please ensure you are logged in.")
        
        # Determine which profile name to show in the hint
        # If we successfully created the session, use its resolved profile.
        # Otherwise fallback to the argument or 'default'.
        target_profile = locals().get('effective_profile') or profile_name or 'default'
        
        print(f"Try running: aws sso login --profile {target_profile}")
        sys.exit(1)

def find_bags(directory):
    try:
        test_directory = os.listdir(directory)
    except OSError:
        sys.exit(f'Please retry with a valid directory of files: {directory}')

    bags = []
    bag_ids = []
    if test_directory:
        all_manifests = glob.iglob(
            os.path.join(directory, '**', 'manifest-md5.txt'),
            recursive=True
        )
        for filepath in all_manifests:
            if '$RECYCLE' not in filepath:
                bag_path = os.path.split(filepath)[0]
                bags.append(bag_path)

        for bag in bags:
            match = re.findall(r'\d{6}', bag)
            if match:
                bag_ids.append(match[-1])
            else:
                bag_ids.append('UnknownBagID')
    return bags, bag_ids

def get_files(source_directory):
    """
    Locates files within a bag.
    Priority Logic:
    1. If 'ServiceCopies' (sc.mp4/sc.json) exist, return ONLY those.
    2. Else if 'EditMasters' (em.flac/em.wav/em.json) exist, return those.
    """
    sc_files = {'paths': [], 'names': [], 'media': [], 'json': []}
    em_files = {'paths': [], 'names': [], 'media': [], 'json': []}

    for root, dirs, files in os.walk(source_directory):
        for file in files:
            if file.startswith('._'):
                continue
            
            path = os.path.join(root, file)
            lower = file.lower()
            
            # Categorize Service Copies (SC)
            if lower.endswith(('sc.mp4', 'sc.json')):
                sc_files['paths'].append(path)
                sc_files['names'].append(file)
                if lower.endswith('.mp4'):
                    sc_files['media'].append(path)
                elif lower.endswith('.json'):
                    sc_files['json'].append(path)
            
            # Categorize Edit Masters (EM)
            elif lower.endswith(('em.wav', 'em.flac', 'em.json')):
                em_files['paths'].append(path)
                em_files['names'].append(file)
                if lower.endswith(('.wav', '.flac')):
                    em_files['media'].append(path)
                elif lower.endswith('.json'):
                    em_files['json'].append(path)

    # Priority Return: If SC found, ignore EM.
    if sc_files['paths']:
        return sc_files['paths'], sc_files['names'], sc_files['media'], sc_files['json']
    elif em_files['paths']:
        return em_files['paths'], em_files['names'], em_files['media'], em_files['json']
    else:
        warnings.warn(f'No valid SC or EM files found in {source_directory}')
        return [], [], [], []

def valid_fn_convention(all_file_list):
    pattern = r'(\w{3}_\d{6}_\w+_(sc|em))'
    invalid_fn_ls = []

    for file in all_file_list:
        try:
            _ = re.search(pattern, file).group(0)
        except AttributeError:
            print(f'{file} not named correctly')
            invalid_fn_ls.append(file)
    if invalid_fn_ls:
        return invalid_fn_ls
    return True

def valid_media_json_match(media_paths_list, json_paths_list):
    media_set = set([os.path.splitext(os.path.basename(i))[0]
                     for i in media_paths_list])
    json_set = set([os.path.splitext(os.path.basename(i))[0]
                    for i in json_paths_list])

    if media_set == json_set:
        return True
    else:
        return media_set.symmetric_difference(json_set)

def valid_json_reference(media_file_list, json_file_list):
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
    for file in json_file_list:
        with open(file, "r", encoding='utf-8-sig') as jsonFile:
            data = json.load(jsonFile)
            barcode = data['bibliographic']['barcode']
            match = re.search(r'^33433\d+', barcode)
            if not match:
                return file
    return True

def check_bucket(s3_client, filenames_list):
    """
    Checks if filenames exist in bucket using boto3.
    Optimized to use list_objects_v2 with a common prefix to reduce API calls.
    Returns a list of FILENAMES (not full paths) that are missing.
    """
    if not filenames_list:
        return []

    # 1. Determine common prefix to narrow down the listing
    #    (e.g., "MDR_123456_")
    common_prefix = os.path.commonprefix(filenames_list)
    
    # 2. Fetch all existing objects with that prefix
    found_keys = set()
    paginator = s3_client.get_paginator('list_objects_v2')
    
    # If common_prefix is empty, this lists the whole bucket.
    # We rely on bag structure having a shared ID/prefix to keep this efficient.
    
    try:
        page_iterator = paginator.paginate(
            Bucket=BUCKET_NAME,
            Prefix=common_prefix
        )

        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    found_keys.add(obj['Key'])
    except ClientError as e:
        print(f"Error listing objects: {e}")
        pass

    to_upload = []

    for file in filenames_list:
        # Check primary key
        if file in found_keys:
            continue
            
        # Fallback check for MP4 variant if FLAC/WAV
        if 'flac' in file or 'wav' in file:
            mp4_key = file.replace('flac', 'mp4').replace('wav', 'mp4')
            if mp4_key in found_keys:
                continue
        
        # If we get here, neither the file nor its variant was found
        to_upload.append(file)

    return to_upload

def file_type_counts(all_file_list):
    mp4_files = [f for f in all_file_list if f.lower().endswith('.mp4')]
    wav_files = [f for f in all_file_list if f.lower().endswith('.wav')]
    flac_files = [f for f in all_file_list if f.lower().endswith('.flac')]
    json_files = [f for f in all_file_list if f.lower().endswith('.json')]
    return len(mp4_files), len(wav_files), len(flac_files), len(json_files)

def transcode_flac(input_path, output_path, dry_run=False):
    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-c:a", "aac",
        "-b:a", "320k",
        "-dither_method", "rectangular",
        "-ar", "44100",
        "-loglevel", "error",
        output_path
    ]
    
    if dry_run:
        print(f"dict[DRY RUN] Would run: {' '.join(command)}")
        return True

    print(f"Transcoding {os.path.basename(input_path)} to temp MP4...")
    result = subprocess.run(command)
    if result.returncode == 0:
        return True
    else:
        print(f"Error transcoding {input_path}")
        return False

def create_modified_json(input_path, output_path, new_ref_filename, dry_run=False):
    if dry_run:
        print(f"[DRY RUN] Would create modified JSON at {output_path} referencing {new_ref_filename}")
        return True

    try:
        with open(input_path, "r", encoding='utf-8-sig') as jsonFile:
            data = json.load(jsonFile)
        
        data['asset']['referenceFilename'] = new_ref_filename
        
        with open(output_path, "w", encoding='utf-8') as jsonFile:
            json.dump(data, jsonFile, indent=4)
        return True
            
    except Exception as e:
        print(f"Failed to create modified JSON: {e}")
        return False

def prepare_transcodes(file_list_to_upload, all_files_in_bag, temp_dir, dry_run=False):
    final_list = []
    processed_json_bases = set()
    
    # Map base filenames to full JSON paths from the entire bag context
    json_map = {}
    for f in all_files_in_bag:
        if f.lower().endswith('.json'):
            base = os.path.splitext(os.path.basename(f))[0]
            json_map[base] = f

    for f in file_list_to_upload:
        if f.lower().endswith('.flac'):
            # Define temp paths
            base_name = os.path.splitext(os.path.basename(f))[0]
            mp4_filename = base_name + ".mp4"
            mp4_temp_path = os.path.join(temp_dir, mp4_filename)
            
            # Transcode (or simulate)
            if transcode_flac(f, mp4_temp_path, dry_run=dry_run):
                final_list.append(mp4_temp_path)
                
                # Handle JSON
                if base_name in json_map:
                    src_json_path = json_map[base_name]
                    json_filename = os.path.basename(src_json_path)
                    json_temp_path = os.path.join(temp_dir, json_filename)
                    
                    if create_modified_json(src_json_path, json_temp_path, mp4_filename, dry_run=dry_run):
                        final_list.append(json_temp_path)
                        processed_json_bases.add(base_name)
                else:
                    print(f"Warning: No matching JSON found for {f}")
            else:
                pass

        elif f.lower().endswith('.json'):
            base_name = os.path.splitext(os.path.basename(f))[0]
            if base_name in processed_json_bases:
                continue
            
            # If this is a standalone JSON upload (or FLAC was missing), 
            # assume target is MP4 and modify it.
            json_filename = os.path.basename(f)
            json_temp_path = os.path.join(temp_dir, json_filename)
            mp4_ref_name = base_name + ".mp4"
            
            if create_modified_json(f, json_temp_path, mp4_ref_name, dry_run=dry_run):
                 final_list.append(json_temp_path)
                 
        else:
            # Non-transcode files (e.g. existing MP4s) - just upload original
            final_list.append(f)
            
    return sorted(list(set(final_list)))

def cp_files(s3_client, file_list, dry_run=False):
    failed_uploads = []
    for filename in sorted(file_list):
        # In dry run, we skip the existence check for temp files because they weren't actually created
        if not dry_run and not os.path.exists(filename):
             print(f"Error: File not found for upload: {filename}")
             failed_uploads.append(filename)
             continue

        key = os.path.basename(filename)
        
        if dry_run:
            print(f"[DRY RUN] Would upload: {filename} to s3://{BUCKET_NAME}/{key}")
        else:
            print(f"Uploading: {key}")
            try:
                s3_client.upload_file(filename, BUCKET_NAME, key)
            except Exception as e:
                 print(f"Failed to upload {filename}: {e}")
                 failed_uploads.append(filename)
    return failed_uploads

def process_single_directory(directory, arguments, s3_client):
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
        'failed_uploads': [],
        'uploaded_counts': {
            'mp4': 0,
            'wav': 0,
            'flac': 0,
            'json': 0
        }
    }

    for bag in sorted(bags):
        all_file_paths, all_files, media_list, json_list = get_files(bag)
        filename_to_path = {os.path.basename(p): p for p in all_file_paths}

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
                
                files_to_process_paths = []

                if arguments.check_only or arguments.check_and_upload:
                    # Note: We perform the REAL S3 check even in Dry Run to give accurate info
                    print(f'Now checking if {bag} is in the bucket:\n')
                    missing_filenames = check_bucket(s3_client, all_files)
                    
                    if missing_filenames:
                        summary['incomplete_in_bucket'].append(bag)
                        print(f'\nNo, {bag} not in the bucket.')
                        if arguments.check_and_upload:
                            files_to_process_paths = [filename_to_path[f] for f in missing_filenames]
                    else:
                        print(f'\nYes, {bag} is in the bucket.')
                else:
                    files_to_process_paths = all_file_paths

                if files_to_process_paths:
                    print(f'Preparing to upload {len(files_to_process_paths)} files for {bag}\n')
                    
                    with tempfile.TemporaryDirectory() as temp_dir:
                        if arguments.transcode:
                            files_to_process_paths = prepare_transcodes(
                                files_to_process_paths, 
                                all_file_paths, 
                                temp_dir,
                                dry_run=arguments.dry_run
                            )

                        mp4_ct, wav_ct, flac_ct, json_ct = file_type_counts(files_to_process_paths)
                        
                        failures = cp_files(s3_client, files_to_process_paths, dry_run=arguments.dry_run)
                        summary['failed_uploads'].extend(failures)
                        
                        summary['uploaded_counts']['mp4'] += mp4_ct
                        summary['uploaded_counts']['wav'] += wav_ct
                        summary['uploaded_counts']['flac'] += flac_ct
                        summary['uploaded_counts']['json'] += json_ct

            else:
                if fn_check != True:
                    summary['invalid_fn_ls'].extend(fn_check)
                if media_json_check != True:
                    summary['fn_mismatch_ls'].append(media_json_check)
                if reference_check != True:
                    summary['json_mismatch_ls'].append(reference_check)
                if barcode_check != True:
                    summary['bc_mismatch_ls'].append(barcode_check)

    return summary

def print_summary(arguments, summary):
    directory = summary['directory']
    print(f"\n=== Summary for {directory} ===")
    print(f"Found {summary['num_bags_found']} bags.")
    print(f"Bag IDs: {summary['bag_ids']}")
    
    uc = summary['uploaded_counts']
    
    prefix = "[DRY RUN] " if arguments.dry_run else ""
    upload_msg = f"{prefix}Uploaded counts: {uc['mp4']} MP4, {uc['wav']} WAV, {uc['flac']} FLAC, {uc['json']} JSON"
    
    issues_msg = f"""
EM or SC issue bags: {summary['em_sc_issue_bags']}
Bags with invalid filename(s): {summary['invalid_fn_ls']}
Media/JSON mismatched bag(s): {summary['fn_mismatch_ls']}
JSON reference mismatched bag(s): {summary['json_mismatch_ls']}
Barcode mismatched bag(s): {summary['bc_mismatch_ls']}"""
    
    if summary['failed_uploads']:
        issues_msg += f"\n\n[ERROR] Failed Uploads ({len(summary['failed_uploads'])} files):\n" + "\n".join(summary['failed_uploads'])

    if arguments.check_only:
        print(issues_msg)
        print(f"Bags needing upload: {summary['incomplete_in_bucket']}")
    else:
        print(upload_msg)
        print(issues_msg)

def main():
    arguments = get_args()
    
    if arguments.dry_run:
        print("\n******************** DRY RUN MODE ********************")
        print("No files will be transcoded or uploaded.")
        print("S3 bucket checks are REAL (read-only).")
        print("******************************************************\n")

    # Initialize S3 client once
    s3_client = get_s3_client(arguments.profile)

    all_summaries = []
    for directory in arguments.directories:
        print(f"\nProcessing directory: {directory}")
        summary = process_single_directory(directory, arguments, s3_client)
        all_summaries.append(summary)
    
    for summary in all_summaries:
        print_summary(arguments, summary)

if __name__ == '__main__':
    main()