#!/usr/bin/env python3

import argparse
import os
import csv
import pandas as pd
import logging
import re
from fmrest import Server
from fmrest.exceptions import FileMakerError 


# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_arguments():
    parser = argparse.ArgumentParser(description="Script to read SPEC AMI IDs from a CSV or Excel file and process them using a Filemaker database.")
    parser.add_argument('-u', '--username', required=True, help="The username for the Filemaker database.")
    parser.add_argument('-p', '--password', required=True, help="The password for the Filemaker database.")
    parser.add_argument('-i', '--input', required=True, help="The path to the input file containing SPEC AMI IDs.")
    parser.add_argument('-o', '--output', required=True, help="The path to the output CSV file for exporting barcodes.")
    return parser.parse_args()

# Environment variables
server = os.getenv('FM_SERVER')
database = os.getenv('FM_DATABASE')
layout = os.getenv('FM_LAYOUT')

if not all([server, database, layout]):
    logging.error("Server, database, and layout need to be set as environment variables.")
    exit(1)

def connect_to_filemaker(server, username, password, database, layout):
    url = f"https://{server}"
    api_version = 'v1'
    fms = Server(url, database=database, layout=layout, user=username, password=password, verify_ssl=True, api_version=api_version)
    try:
        fms.login()
        logging.info("Successfully connected to the FileMaker database.")
        return fms
    except Exception as e:
        logging.error(f"Failed to connect to Filemaker server: {e}")
        return None

def read_spec_ami_ids(file_path):
    ids = []
    try:
        if file_path.endswith('.csv'):
            with open(file_path, mode='r', encoding='utf-8') as file:
                reader = csv.reader(file)
                first_row = next(reader, None)
                if first_row and any(not item.isdigit() for item in first_row):
                    column_index = first_row.index('SPEC_AMI_ID') if 'SPEC_AMI_ID' in first_row else 0
                else:
                    column_index = 0  # Assume the ID is in the first column
                    if re.match(r"^\d{6}$", first_row[0]):
                        ids.append(first_row[0])
                for row in reader:
                    if re.match(r"^\d{6}$", row[column_index]):
                        ids.append(row[column_index])
        elif file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path, dtype=str)
            for sheet_name, sheet_df in df.items():
                if 'SPEC_AMI_ID' in sheet_df.columns:
                    ids.extend(sheet_df['SPEC_AMI_ID'].dropna().tolist())
    except Exception as e:
        logging.error(f"Failed to read input file: {e}")
    return ids

def process_records(fms, spec_ami_ids, output_path):
    output_data = []
    not_found_ids = []

    for ami_id in sorted(set(spec_ami_ids)):
        logging.info(f"Attempting to find: {ami_id}")
        try:
            found_records = fms.find([{"ref_ami_id": ami_id}])
            for record in found_records:
                record_data = record.to_dict()
                print(record_data)  # Debug print to check data structure

                # Extract format types
                format_1 = record_data.get('format_1', '')
                format_2 = record_data.get('format_2', '')
                format_3 = record_data.get('format_3', '')

                # Append the formats instead of the barcode
                output_data.append([ami_id, format_1, format_2, format_3])
        except FileMakerError as e:
            if "No records match the request" in str(e):
                not_found_ids.append(ami_id)
                logging.info(f"No record found for ID: {ami_id}")
            else:
                logging.error(f"An error occurred while searching for ID {ami_id}: {e}")

    # Write the output to a CSV file
    with open(output_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['SPEC_AMI_ID', 'Format 1', 'Format 2', 'Format 3'])  # Adjust the header
        writer.writerows(output_data)

    if not_found_ids:
        logging.info(f"IDs not found: {not_found_ids}")
        with open('not_found_ids.csv', 'w', newline='', encoding='utf-8') as nf_file:
            writer = csv.writer(nf_file)
            writer.writerow(['Not Found SPEC_AMI_IDs'])
            writer.writerows([[id] for id in not_found_ids])

    return not_found_ids  # Optionally return the list of not found IDs



def main():
    args = parse_arguments()
    fms = connect_to_filemaker(server, args.username, args.password, database, layout)
    if fms:
        spec_ami_ids = read_spec_ami_ids(args.input)
        process_records(fms, spec_ami_ids, args.output)

if __name__ == "__main__":
    main()
