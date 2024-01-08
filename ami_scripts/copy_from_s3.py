#!/usr/bin/env python3
import argparse
import csv
import re
import subprocess
import json


def parse_arguments():
    parser = argparse.ArgumentParser(description='Manage files from an AWS S3 bucket.')
    parser.add_argument('-n', '--numbers', required=True, help='CSV file with numbers.')
    parser.add_argument('-i', '--input', required=True, help='Input CSV file to search in.')
    parser.add_argument('-d', '--destination', required=True, help='Local destination path.')
    parser.add_argument('-b', '--bucket', required=True, help='AWS S3 bucket name.')
    parser.add_argument('-e', '--extension', required=True, choices=['mkv', 'mov', 'mp4', 'flac', 'wav'], help='File extension to filter by.')
    parser.add_argument('-m', '--mode', required=True, choices=['copy', 'restore'], help='Operation mode: "copy" for immediate copy, "restore" to initiate a Glacier restore process.')
    return parser.parse_args()


def extract_id_from_filename(filename):
    match = re.search(r'_(\d{6})_', filename)
    return match.group(1) if match else None


def read_numbers(file_path):
    with open(file_path, 'r') as file:
        return [str(int(row[0])) for row in csv.reader(file) if row]


def find_files(input_csv, numbers_list, extension):
    files_to_copy = []
    numbers_not_found = set(numbers_list)
    regex_pattern = fr'_(\d{{6}}).+\.{extension}'

    with open(input_csv, 'r') as file:
        for line in file:
            match = re.search(regex_pattern, line)
            if match:
                number = match.group(1)
                if number in numbers_list:
                    files_to_copy.append(line.strip().split()[-1])
                    numbers_not_found.discard(number)

    if numbers_not_found:
        print("Numbers not found in the input CSV (AWS Bucket List):", list(numbers_not_found))

    return files_to_copy


def initiate_restores(files_to_copy, bucket):
    restore_count = 0
    unique_objects = set()

    for file_path in files_to_copy:
        file_id = extract_id_from_filename(file_path)
        if file_id:
            unique_objects.add(file_id)

        restore_command = f'aws s3api restore-object --bucket {bucket} --key {file_path} --restore-request Days=5'
        print(f"Initiating restore: {restore_command}")
        result = subprocess.run(restore_command, shell=True)
        if result.returncode == 0:
            restore_count += 1
        else:
            print(f"Failed to initiate restore for: {file_path}")

    print(f"Restore initiated for {restore_count} files, representing {len(unique_objects)} unique objects.")


def check_restore_status(files_to_copy, bucket):
    for file_path in files_to_copy:
        head_command = f'aws s3api head-object --bucket {bucket} --key {file_path}'
        process = subprocess.run(head_command, shell=True, capture_output=True, text=True)
        
        if process.returncode == 0:
            response = json.loads(process.stdout)
            restore_status = response.get('Restore', '')
            if 'ongoing-request="true"' in restore_status:
                print(f"Restore in progress for: {file_path}")
            elif 'ongoing-request="false"' in restore_status:
                print(f"Restore completed for: {file_path}")
            else:
                print(f"No restore information found for: {file_path}, it might not be in Glacier.")
        else:
            print(f"Error checking restore status for: {file_path}")


def copy_files(files_to_copy, destination, bucket):
    copied_count = 0
    unique_objects = set()

    for file_path in files_to_copy:
        file_id = extract_id_from_filename(file_path)
        if file_id:
            unique_objects.add(file_id)

        copy_command = f'aws s3 cp s3://{bucket}/{file_path} {destination}'
        print(f"Executing: {copy_command}")
        result = subprocess.run(copy_command, shell=True)
        if result.returncode == 0:
            copied_count += 1
        else:
            print(f"Failed to copy: {file_path}")

    print(f"{copied_count} files copied, representing {len(unique_objects)} unique objects.")

def main():
    args = parse_arguments()
    numbers_list = read_numbers(args.numbers)
    files_to_copy = find_files(args.input, numbers_list, args.extension)
    
    if args.mode == 'restore':
        initiate_restores(files_to_copy, args.bucket)
    elif args.mode == 'copy':
        copy_files(files_to_copy, args.destination, args.bucket)

if __name__ == '__main__':
    main()