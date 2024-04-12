#!/usr/bin/env python3

import argparse
import csv
import os
import re
from fmrest import Server

# Define command line arguments
parser = argparse.ArgumentParser(description="Script to read SPEC AMI IDs from a CSV and process them using a Filemaker database.")
parser.add_argument('-u', '--username', help="The username for the Filemaker database.", required=True)
parser.add_argument('-p', '--password', help="The password for the Filemaker database.", required=True)
parser.add_argument('-i', '--input', help="The path to the CSV file containing SPEC AMI IDs.", required=True)
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

# Function to read SPEC AMI IDs from CSV
def read_spec_ami_ids(csv_file_path):
    ids = []
    try:
        with open(csv_file_path, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            first_row = next(reader, None)  # Read the first row to check if it's a header

            # Check if the first row is a header or a valid ID
            if first_row and re.match(r"^\d{6}$", first_row[0]):
                ids.append(first_row[0])  # It's a valid ID, not a header
                for row in reader:
                    ids.append(row[0])
            elif first_row:
                for row in reader:
                    if re.match(r"^\d{6}$", row[0]):
                        ids.append(row[0])  # Only add if it's a valid six-digit number
    except Exception as e:
        print(f"Failed to read CSV file: {e}")
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
        
        # Export barcodes sorted by AMI ID to CSV
        with open(args.output, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['AMI ID', 'Barcode'])
            
            for ami_id, barcode in sorted(ami_id_to_barcode.items()):
                writer.writerow([ami_id, barcode])
        
        print(f"Exported {len(ami_id_to_barcode)} unique barcodes to {args.output}, sorted by AMI ID.")
        fms.logout()
    else:
        print("Failed to connect to the Filemaker server.")
