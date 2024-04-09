#!/usr/bin/env python3

import argparse
import pandas as pd

def parse_arguments():
    parser = argparse.ArgumentParser(description='Compare spec and file list CSVs.')
    parser.add_argument('-f', '--files', required=True, help='Path to the CSV of media files.')
    parser.add_argument('-s', '--spec', required=True, help='Path to the CSV of spec objects.')
    parser.add_argument('-o', '--output', required=True, help='Path to the output CSV for missing IDs.')
    return parser.parse_args()

def read_spec_csv(spec_path):
    spec_df = pd.read_csv(spec_path, usecols=['ref_ami_id', 'migration_status'], encoding='ISO-8859-1')
    migrated_df = spec_df[spec_df['migration_status'] == 'Migrated']
    return set(migrated_df['ref_ami_id'].astype(str))  # Cast to string to ensure consistent ID format

def extract_ids_from_filenames(files_df):
    files_df['id'] = files_df['filename'].str.extract(r'mao_(\d{6})_')
    return set(files_df['id'].dropna())

def main():
    args = parse_arguments()
    
    # Read and filter spec CSV for migrated objects
    migrated_ids = read_spec_csv(args.spec)
    
    # Read the file list CSV and extract IDs from filenames
    files_df = pd.read_csv(args.files, names=['filename'])  # Assumes the file has no header and only filenames
    file_ids = extract_ids_from_filenames(files_df)
    
    # Find migrated objects with no files
    missing_files = migrated_ids - file_ids
    found_files = migrated_ids.intersection(file_ids)
    
    # Print counts of missing and found IDs
    print(f'Count of missing IDs: {len(missing_files)}')
    print(f'Count of found IDs: {len(found_files)}')

    # Export missing IDs to a CSV file
    pd.Series(list(missing_files)).to_csv(args.output, index=False, header=False)

    if missing_files:
        print(f'Migrated objects missing files have been written to {args.output}')
    else:
        print('All migrated objects have files.')

if __name__ == "__main__":
    main()

