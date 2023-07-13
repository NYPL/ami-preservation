#!/usr/bin/env python3
import os
import argparse
import random
import subprocess
import shutil

def check_rawcooked():
    if shutil.which("rawcooked") is None:
        print("rawcooked is not installed. Please install it using the following commands:")
        print("brew tap mediaarea/mediaarea")
        print("brew install rawcooked")
        exit(1)

def traverse_directory(directory):
    print(f"Searching for MKV files in {directory}...")
    mkv_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".mkv"):
                mkv_files.append(os.path.join(root, file))
    print(f"Found {len(mkv_files)} MKV files.")
    return mkv_files

def process_files(files, percentage):
    number_to_process = round(len(files) * (percentage/100))
    print(f"Processing {number_to_process} files ({percentage}% of {len(files)}) with rawcooked...")
    files_to_process = random.sample(files, number_to_process)
    success_count = 0
    failure_count = 0
    for file in files_to_process:
        print(f"Processing file: {file}")
        command = ['rawcooked', '--check', file]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
        output = ''
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
            output += line
        if 'Decoding was checked, no issue detected.' in output:
            success_count += 1
        elif 'Decoding was checked, issues detected, see below.' in output:
            failure_count += 1
    print(f"Finished processing {number_to_process} files. {success_count} files processed successfully, {failure_count} files failed.")

def main():
    parser = argparse.ArgumentParser(description="Process a given percentage of MKV files in a directory with rawcooked.")
    parser.add_argument('-d', '--directory', type=str, required=True, help="Directory containing MKV files.")
    parser.add_argument('-p', '--percentage', type=int, default=10, help="Percentage of MKV files to process.")
    
    args = parser.parse_args()

    check_rawcooked()
    files = traverse_directory(args.directory)
    process_files(files, args.percentage)

if __name__ == "__main__":
    main()
