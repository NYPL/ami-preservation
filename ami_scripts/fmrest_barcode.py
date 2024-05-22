#!/usr/bin/env python3

import argparse
import csv
import os
import re
import pandas as pd
from fmrest import Server

# Define command line arguments
parser = argparse.ArgumentParser(description="Script to read SPEC AMI IDs from a CSV or Excel file and process them using a Filemaker database.")
parser.add_argument('-u', '--username', help="The username for the Filemaker database.", required=True)
parser.add_argument('-p', '--password', help="The password for the Filemaker database.", required=True)
parser.add_argument('-i', '--input', help="The path to the input file containing SPEC AMI IDs.", required=True)
parser.add_argument('-o', '--output', help="The path to the output CSV file for exporting barcodes.", required=True)

args = parser.parse_args()

# Environment variables
server = os.getenv('FM_SERVER')
database = os.getenv('FM_DATABASE')
layout = os.getenv('FM_LAYOUT')

if not all([server, database, layout]):
    print("Server, database, and layout need to be set as environment variables.")
    exit(1)

# Function to connect to Filemaker database
def connect_to_filemaker(server, username, password, database, layout):
    url = f"https://{server}"
    api_version = 'v1'
    fms = Server(url, database=database, layout=layout, user=username, password=password, verify_ssl=True, api_version=api_version)
    
    try:
        fms.login()
        print("Successfully connected to the FileMaker database.")
        return fms
    except Exception as e:
        print(f"Failed to connect to Filemaker server: {e}")
        return None

# Function to read SPEC AMI IDs from input file
def read_spec_ami_ids(file_path):
    ids = []
    try:
        if file_path.endswith('.csv'):
            with open(file_path, mode='r', encoding='utf-8') as file:
                reader = csv.reader(file)
                # Attempt to read the first row
                first_row = next(reader, None)
                if first_row:
                    # Check if the first row is likely a header by checking for non-digit entries
                    if any(not item.isdigit() for item in first_row):
                        # It's a header, determine the index of the 'SPEC_AMI_ID' column
                        column_index = first_row.index('SPEC_AMI_ID') if 'SPEC_AMI_ID' in first_row else 0
                    else:
                        # It's not a header, treat this as data
                        if re.match(r"^\d{6}$", first_row[0]):
                            ids.append(first_row[0])
                        column_index = 0  # Assume the ID is in the first column
                    # Process the rest of the rows
                    for row in reader:
                        if re.match(r"^\d{6}$", row[column_index]):
                            ids.append(row[column_index])
        elif file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path, sheet_name=None)
            valid_sheet = None
            for sheet_name, sheet_df in df.items():
                if 'SPEC_AMI_IDs' in sheet_name or re.search(r"spec_ami_ids", sheet_name, re.IGNORECASE):
                    valid_sheet = sheet_df
                    break
            if valid_sheet is not None:
                if 'SPEC_AMI_ID' in valid_sheet.columns:
                    for id in valid_sheet['SPEC_AMI_ID']:
                        if re.match(r"^\d{6}$", str(id)):
                            ids.append(str(id))
                else:
                    print("SPEC_AMI_ID column not found. Please check the Excel file.")
            else:
                print("Suitable sheet not found. Please check the Excel file.")
    except Exception as e:
        print(f"Failed to read input file: {e}")
    return ids

if __name__ == "__main__":
    fms = connect_to_filemaker(server, args.username, args.password, database, layout)
    if fms:
        spec_ami_ids = read_spec_ami_ids(args.input)
        ami_id_to_barcode = {}
        
        for ami_id in spec_ami_ids:
            print(f"Attempting to find: {ami_id}")
            query = [{"ref_ami_id": ami_id}]
            try:
                found_records = fms.find(query)
                found_records_list = list(found_records)
                if found_records_list:
                    barcode = getattr(found_records_list[0], 'id_barcode', None)
                    if barcode:
                        ami_id_to_barcode[ami_id] = barcode
                        print(f"Found and added barcode: {barcode} for AMI ID: {ami_id}")
                    else:
                        print(f"No barcode found for AMI ID: {ami_id}")
                else:
                    print(f"No records found for ID: {ami_id}")
            except Exception as e:
                print(f"An error occurred while searching for ID {ami_id}: {e}")
        
        with open(args.output, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['AMI ID', 'Barcode'])
            for ami_id, barcode in sorted(ami_id_to_barcode.items()):
                writer.writerow([ami_id, barcode])
        
        print(f"Exported {len(ami_id_to_barcode)} unique barcodes to {args.output}, sorted by AMI ID.")
        fms.logout()
    else:
        print("Failed to connect to the Filemaker server.")
