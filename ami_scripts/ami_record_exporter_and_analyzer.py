#!/usr/bin/env python3

import argparse
import csv
import os
import re
import pandas as pd
from fmrest import Server
from collections import defaultdict
import xml.etree.ElementTree as ET
from bookops_nypl_platform import PlatformSession, PlatformToken
import logging
import requests
from openpyxl.styles import Font

def parse_arguments():
    parser = argparse.ArgumentParser(description="Script to read SPEC AMI IDs from a CSV or Excel file and process them using a Filemaker database and APIs.")
    parser.add_argument('-u', '--username', help="The username for the Filemaker database.", required=True)
    parser.add_argument('-p', '--password', help="The password for the Filemaker database.", required=True)
    parser.add_argument('-i', '--input', help="The path to the input file containing SPEC AMI IDs.", required=True)
    parser.add_argument('-o', '--output', help="The path to the output XLSX file for exported data.", required=True)
    return parser.parse_args()

# Environment variables
server = os.getenv('FM_SERVER')
database = os.getenv('FM_DATABASE')
layout = os.getenv('FM_LAYOUT')

if not all([server, database, layout]):
    logging.error("Server, database, and layout need to be set as environment variables.")
    exit(1)

def create_platform_session():
    client_id = os.getenv("OAUTH_CLIENT_ID")
    client_secret = os.getenv("OAUTH_CLIENT_SECRET")
    oauth_server = os.getenv("OAUTH_SERVER")
    try:
        token = PlatformToken(client_id, client_secret, oauth_server)
        session = PlatformSession(authorization=token)
        logging.info("Successfully connected to the Platform API.")
        return session
    except Exception as e:
        logging.error(f"Failed to connect to Platform API: {e}")
        return None

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

def get_sierra_item(session, barcode):
    try:
        response = session.get_item_list(barcode=barcode)
        if response.status_code == 200 and response.json()["data"]:
            return response.json()
        else:
            return {"error": "Item barcode does not exist in Sierra database."}
    except Exception as e:
        logging.error(f"Error fetching item from Sierra: {e}")
        return {"error": str(e)}

def extract_sierra_location(data):
    if "error" in data:
        return data["error"], data["error"]
    try:
        location_value = data["data"][0]["fixedFields"]["79"]["value"]
        location_display = data["data"][0]["fixedFields"]["79"]["display"]
        return location_value, location_display
    except (KeyError, IndexError):
        return "N/A", "N/A"

def get_scsb_availability(barcode):
    """
    Retrieves the item availability from the SCSB API.
    """
    api_key = os.getenv("SCSB_API_KEY")
    url = os.getenv("SCSB_API_URL")  
    headers = {
        'accept': 'application/json',
        'api_key': api_key,
        'Content-Type': 'application/json'
    }
    payload = {
        "barcodes": [barcode]
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return [{"error": "Item barcode doesn't exist in SCSB database."}]
    except Exception as e:
        logging.error(f"SCSB API request failed: {e}")
        return [{"error": str(e)}]

def extract_scsb_data(json_response):
    if not json_response:
        logging.error("Empty JSON data received.")
        return {'Availability': 'N/A'}
    if "error" in json_response:
        return {'Availability': json_response["error"]}
    
    item_availability = json_response[0].get('itemAvailabilityStatus', 'N/A')
    return {'Availability': item_availability}

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

def process_records(fms, platform_session, spec_ami_ids, ami_id_details, box_summary):
    customer_code = "NYPL"  # Set the appropriate customer code
    spec_ami_id_set = set(spec_ami_ids)  # Convert to set for faster lookup

    for ami_id in sorted(spec_ami_ids):
        logging.info(f"Attempting to find: {ami_id}")
        found_records = fms.find([{"ref_ami_id": ami_id}])

        for record in found_records:
            record_data = record.to_dict()
            box_barcode = record_data.get('OBJECTS_parent_from_OBJECTS::id_barcode', None)

            # Initialize summary data if not already done
            box_name = record_data.get('OBJECTS_parent_from_OBJECTS::name_d_calc', 'No Box')
            if box_name not in box_summary:
                box_summary[box_name] = {
                    'Box Barcode': box_barcode or 'No Barcode',
                    'SPEC Box Location': record_data.get('OBJECTS_parent_from_OBJECTS::ux_loc_active_d', 'Not Specified'),
                    'Total Count': 0,
                    'Formats': defaultdict(int),
                    'SCSB Availabilities': set(),
                    'Total Box Items': 0  # Track total items in box
                }

            if not box_barcode:
                # Treat items without a box barcode as single items
                ami_barcode = record_data.get('id_barcode', None)
                if ami_barcode:
                    logging.info(f"Handling as a single item in SCSB: {ami_barcode}")
                    try:
                        scsb_json = get_scsb_availability(ami_barcode)
                        scsb_data = extract_scsb_data(scsb_json)
                        scsb_availability = scsb_data.get('Availability', 'N/A')
                        logging.info(f"SCSB Data retrieved for single item {ami_barcode}: {scsb_data}")
                    except Exception as e:
                        logging.error(f"Failed to retrieve or parse SCSB data for single item {ami_barcode}: {e}")
                        scsb_availability = 'N/A'
                    sierra_location_code, sierra_location_display = 'N/A', 'N/A'
                else:
                    scsb_availability = 'No Barcode for Single Item'
                    sierra_location_code, sierra_location_display = 'N/A', 'N/A'
                update_details_and_summary(record_data, ami_id, ami_barcode, sierra_location_code, sierra_location_display, ami_id_details, box_summary, scsb_availability)
                logging.info(f"No box barcode found for AMI ID {ami_id}, handled as a single item with barcode: {ami_barcode}")
            else:
                # Fetch all items in the box if a box barcode is present
                box_records = fms.find([{"OBJECTS_parent_from_OBJECTS::id_barcode": box_barcode}])
                box_records_list = list(box_records)  # Convert Foundset to list for easier handling
                logging.info(f"Found {len(box_records_list)} items in box {box_name} with barcode {box_barcode}")
                
                # Update box summary with the correct barcode and SPEC location
                box_summary[box_name]['Box Barcode'] = box_barcode
                box_summary[box_name]['SPEC Box Location'] = record_data.get('OBJECTS_parent_from_OBJECTS::ux_loc_active_d', 'Not Specified')
                box_summary[box_name]['Total Box Items'] = len(box_records_list)

                # Handle as normal if there is a box barcode
                platform_data = get_sierra_item(platform_session, box_barcode)
                sierra_location_code, sierra_location_display = extract_sierra_location(platform_data)
                try:
                    scsb_json = get_scsb_availability(box_barcode)
                    scsb_data = extract_scsb_data(scsb_json)
                    scsb_availability = scsb_data.get('Availability', 'N/A')
                    logging.info(f"SCSB Data retrieved for {box_barcode}: {scsb_data}")
                except Exception as e:
                    logging.error(f"Failed to retrieve or parse SCSB data for barcode {box_barcode}: {e}")
                    scsb_availability = 'N/A'

                update_details_and_summary(record_data, ami_id, box_barcode, sierra_location_code, sierra_location_display, ami_id_details, box_summary, scsb_availability)
                logging.info(f"Sierra Data retrieved for AMI ID {ami_id}: Barcode {box_barcode}, Location Code {sierra_location_code}, Location Name {sierra_location_display}")

                # Increment requested item count for each AMI ID processed
                box_summary[box_name]['Total Count'] += 1

def get_item_format(record_data):
    format_2 = record_data.get('format_2', '')
    format_3 = record_data.get('format_3', '')
    if len(format_3) == 0:
        return format_2
    else:
        return format_3

def update_details_and_summary(record_data, ami_id, box_barcode, sierra_location_code, sierra_location_display, ami_id_details, box_summary, scsb_availability):
    # Default values for missing box barcodes
    box_name = record_data.get('OBJECTS_parent_from_OBJECTS::name_d_calc', 'No Box')
    box_barcode = record_data.get('OBJECTS_parent_from_OBJECTS::id_barcode', 'No Barcode')

    ami_id_detail = {
        'AMI ID': ami_id,
        'Barcode': record_data.get('id_barcode', None),
        'Format': get_item_format(record_data),
        'Migration Status': record_data.get('OBJECTS_MIGRATION_STATUS_active::migration_status', None),
        'SPEC Item Location': record_data.get('ux_loc_active_d', ''),
        'Box Name': box_name,
        'Box Barcode': box_barcode,
        'Sierra Location Code': sierra_location_code,
        'Sierra Location Name': sierra_location_display,
        'SCSB Availability': scsb_availability
    }
    ami_id_details.append(ami_id_detail)

    if box_name not in box_summary:
        box_summary[box_name] = {
            'Box Barcode': box_barcode,
            'SPEC Box Location': record_data.get('OBJECTS_parent_from_OBJECTS::ux_loc_active_d', 'Not Specified'),
            'Total Count': 0,
            'Formats': defaultdict(int),
            'SCSB Availabilities': set(),
            'Total Box Items': 0
        }

    box_summary[box_name]['Formats'][get_item_format(record_data)] += 1
    box_summary[box_name]['SCSB Availabilities'].add(scsb_availability)

def prepare_summary_dataframes(box_summary):
    overview = []
    formats = []
    for box_name, details in box_summary.items():
        overview.append({
            'Box Name': box_name,
            'Box Barcode': details['Box Barcode'],
            'SPEC Box Location': details['SPEC Box Location'],
            'Total Requested Items': details['Total Count'],
            'Remaining Items in Box': details['Total Box Items'] - details['Total Count'],
            'SCSB Availability': ', '.join(details['SCSB Availabilities'])  # Join all unique availabilities
        })
        for format_name, count in details['Formats'].items():
            formats.append({
                'Box Name': box_name,
                'Format': format_name,
                'Count': count
            })

    # Create DataFrames
    overview_df = pd.DataFrame(overview)
    formats_df = pd.DataFrame(formats)

    # Group by Box Name and Format, summing the counts
    formats_df = formats_df.groupby(['Box Name', 'Format']).sum().reset_index()
    
    # Sorting for better readability
    formats_df = formats_df.sort_values(by=['Box Name', 'Format'])

    # Calculate and append total row
    total_items = formats_df['Count'].sum()
    total_row = pd.DataFrame([{'Box Name': 'Total', 'Format': '', 'Count': total_items}], columns=['Box Name', 'Format', 'Count'])
    formats_df = pd.concat([formats_df, total_row], ignore_index=True)

    return overview_df, formats_df

def export_to_excel(output_path, ami_id_details, box_summary):
    details_df = pd.DataFrame(ami_id_details)
    overview_df, formats_df = prepare_summary_dataframes(box_summary)

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        details_df.to_excel(writer, sheet_name='AMI ID Details', index=False)
        overview_df.to_excel(writer, sheet_name='Box Summary', index=False)
        formats_df.to_excel(writer, sheet_name='Format Counts', index=False)

        # Accessing the workbook and the specific sheet
        workbook = writer.book
        format_sheet = writer.sheets['Format Counts']

        # Apply bold formatting to the last row (total row) and 'Count' column if it's the total row
        for row in format_sheet.iter_rows(min_row=1, max_row=format_sheet.max_row, min_col=1, max_col=3):
            if row[0].value == 'Total':  # Assuming 'Total' is in the first column
                for cell in row:
                    cell.font = Font(bold=True)
            if row[0].value == 'Total' and row[2].column == 3:  # The column index for 'Count' is 3
                row[2].font = Font(bold=True)

        # Adjusting column widths
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for col in worksheet.columns:
                max_length = 0
                column = col[0].column_letter  # Get the column letter
                for cell in col:
                    try:  # Necessary to avoid error on empty cells
                        if len(str(cell.value)) > max_length:
                            max_length = len(cell.value)
                    except:
                        pass
                adjusted_width = max_length + 2  # Adding a little extra space
                worksheet.column_dimensions[column].width = adjusted_width

        logging.info(f"Exported details to {output_path} with sheets: 'AMI ID Details', 'Box Summary', and 'Format Counts'.")

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    args = parse_arguments()
    logging.info("Starting the application...")

    fms = connect_to_filemaker(server, args.username, args.password, database, layout)
    if not fms:
        logging.error("Failed to connect to the Filemaker server.")
        return

    spec_ami_ids = read_spec_ami_ids(args.input)
    ami_id_details = []
    box_summary = defaultdict(lambda: {
        'Box Barcode': 'No Barcode',
        'SPEC Box Location': 'Not Specified',
        'Total Count': 0,
        'Formats': defaultdict(int),
        'SCSB Availabilities': set(),
        'Total Box Items': 0
    })

    platform_session = None  # Define platform_session outside the try block to ensure it's always defined
    try:
        platform_session = create_platform_session()
        process_records(fms, platform_session, spec_ami_ids, ami_id_details, box_summary)
        export_to_excel(args.output, ami_id_details, box_summary)
    except Exception as e:
        logging.error(f"Error during processing: {e}")
    finally:
        if platform_session:
            logging.info("Cleaning up platform session...")
        fms.logout()
        logging.info("Processing completed.")

if __name__ == "__main__":
    main()
