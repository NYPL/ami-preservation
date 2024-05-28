#!/usr/bin/env python3

import argparse
import csv
import os
import re
import pandas as pd
from fmrest import Server
from collections import defaultdict

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
            df = pd.read_excel(file_path, sheet_name=None)
            for sheet_name, sheet_df in df.items():
                if 'SPEC_AMI_IDs' in sheet_name or re.search(r"spec_ami_ids", sheet_name, re.IGNORECASE):
                    if 'SPEC_AMI_ID' in sheet_df.columns:
                        ids.extend(sheet_df['SPEC_AMI_ID'].dropna().astype(str).tolist())
    except Exception as e:
        print(f"Failed to read input file: {e}")
    return ids

if __name__ == "__main__":
    fms = connect_to_filemaker(server, args.username, args.password, database, layout)
    if fms:
        spec_ami_ids = read_spec_ami_ids(args.input)
        ami_id_details = []
        box_summary = {}

        for ami_id in sorted(spec_ami_ids):
            print(f"Attempting to find: {ami_id}")
            query = [{"ref_ami_id": ami_id}]
            found_records = fms.find(query)

            for record in found_records:
                record_data = record.to_dict()
                barcode = record_data.get('id_barcode', None)
                migration_status = record_data.get('OBJECTS_MIGRATION_STATUS_active::migration_status', None)
                box_name = str(record_data.get('OBJECTS_parent_from_OBJECTS::name_d_calc', ''))
                box_barcode = str(record_data.get('OBJECTS_parent_from_OBJECTS::id_barcode', ''))
                container_location = str(record_data.get('OBJECTS_parent_from_OBJECTS::ux_loc_active_d', ''))
                item_location = str(record_data.get('ux_loc_active_d', ''))
                format3 = record_data.get('format_3', '')

                ami_id_details.append({
                    'AMI ID': ami_id,
                    'Barcode': barcode,
                    'Format': format3,
                    'Migration Status': migration_status,
                    'Item Location': item_location,
                    'Box Name': box_name,
                    'Box Barcode': box_barcode,
                    'Box Location': container_location
                })
                print(f"Found and added details for AMI ID: {ami_id}")

                if box_name:
                    if box_name not in box_summary:
                        box_summary[box_name] = {
                            'Box Barcode': box_barcode,
                            'Box Location': container_location,
                            'Total Count': 0,
                            'Formats': {}
                        }
                    box_summary[box_name]['Total Count'] += 1
                    if format3 in box_summary[box_name]['Formats']:
                        box_summary[box_name]['Formats'][format3] += 1
                    else:
                        box_summary[box_name]['Formats'][format3] = 1

        # Convert list to DataFrame
        details_df = pd.DataFrame(ami_id_details)

        # Prepare summary data for Excel
        summary_overview = []
        summary_formats = []

        for box_name, details in box_summary.items():
            summary_overview.append({
                'Box Name': box_name,
                'Box Barcode': details['Box Barcode'],
                'Box Location': details['Box Location'],
                'Total Requested Items': details['Total Count']
            })

            for format_name, count in details['Formats'].items():
                summary_formats.append({
                    'Box Name': box_name,
                    'Format': format_name,
                    'Count': count
                })

        overview_df = pd.DataFrame(summary_overview)
        formats_df = pd.DataFrame(summary_formats)

        # Write to Excel
        with pd.ExcelWriter(args.output, engine='openpyxl') as writer:
            details_df.to_excel(writer, sheet_name='AMI ID Details', index=False)
            overview_df.to_excel(writer, sheet_name='Box Summary', index=False)
            formats_df.to_excel(writer, sheet_name='Box Summary', startrow=len(overview_df) + 3, index=False)

        print(f"Exported details to {args.output} with sheets: 'AMI ID Details' and 'Box Summary'.")
        fms.logout()
    else:
        print("Failed to connect to the Filemaker server.")
