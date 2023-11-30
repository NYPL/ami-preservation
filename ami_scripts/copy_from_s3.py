#!/usr/bin/env python3
import argparse
import csv
import re
import subprocess

def parse_arguments():
    parser = argparse.ArgumentParser(description='Copy specified files from an AWS S3 bucket.')
    parser.add_argument('-n', '--numbers', required=True, help='CSV file with numbers')
    parser.add_argument('-i', '--input', required=True, help='Input CSV file to search in')
    parser.add_argument('-d', '--destination', required=True, help='Local destination path')
    parser.add_argument('-b', '--bucket', required=True, help='AWS S3 bucket name')
    return parser.parse_args()

def read_numbers(file_path):
    with open(file_path, 'r') as file:
        return [str(int(row[0])) for row in csv.reader(file) if row]

def find_files(input_csv, numbers_list):
    files_to_copy = []
    numbers_not_found = set(numbers_list)
    regex_pattern = r'_(\d{6})_'

    with open(input_csv, 'r') as file:
        for line in file:
            match = re.search(regex_pattern, line)
            if match:
                number = match.group(1)
                if number in numbers_list and number in numbers_not_found:
                    files_to_copy.append(line.strip().split()[-1])
                    numbers_not_found.remove(number)

    if numbers_not_found:
        print("Numbers not found in the input CSV (EAVie List):", list(numbers_not_found))

    return files_to_copy

def copy_files(files_to_copy, destination, bucket):
    for file_base_name in files_to_copy:
        base_name_without_extension = file_base_name.rsplit('.', 1)[0]
        json_file_name = f"{base_name_without_extension}.json"
        mp4_file_name = f"{base_name_without_extension}.mp4"

        aws_command_json = f'aws s3 cp s3://{bucket}/{json_file_name} {destination}'
        print(f"Executing: {aws_command_json}")
        subprocess.run(aws_command_json, shell=True)

        aws_command_mp4 = f'aws s3 cp s3://{bucket}/{mp4_file_name} {destination}'
        print(f"Executing: {aws_command_mp4}")
        subprocess.run(aws_command_mp4, shell=True)

def main():
    args = parse_arguments()
    numbers_list = read_numbers(args.numbers)
    files_to_copy = find_files(args.input, numbers_list)
    copy_files(files_to_copy, args.destination, args.bucket)

if __name__ == '__main__':
    main()
