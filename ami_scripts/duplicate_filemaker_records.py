#!/usr/bin/env python3

import os
import jaydebeapi
import logging
from pathlib import Path
import argparse
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Script to duplicate FileMaker records for MP4 derivatives.')
parser.add_argument('-d', '--directory', required=True, help='Path to the directory containing ISO and MP4 files.')
parser.add_argument('--dev-server', action='store_true', help='Connect to the DEV server instead of the production server.')
args = parser.parse_args()

# Determine which server to connect to
if args.dev_server:
    server_ip = os.getenv('FM_DEV_SERVER')
    logging.info("Connecting to the test server.")
else:
    server_ip = os.getenv('FM_SERVER')
    logging.info("Connecting to the production server.")

# Load other environment variables
database_name = os.getenv('AMI_DATABASE')
username = os.getenv('AMI_DATABASE_USERNAME')
password = os.getenv('AMI_DATABASE_PASSWORD')
jdbc_path = os.path.expanduser('~/Desktop/ami-preservation/ami_scripts/jdbc/fmjdbc.jar')

# Connect to the database
def connect_to_database():
    try:
        conn = jaydebeapi.connect(
            'com.filemaker.jdbc.Driver',
            f'jdbc:filemaker://{server_ip}/{database_name}',
            [username, password],
            jdbc_path
        )
        logging.info("Connected to the database.")
        return conn
    except Exception as e:
        logging.error(f"Failed to connect to the database: {e}")
        return None

# Crawl directory and map ISO files to MP4s
def crawl_directory(directory):
    file_map = defaultdict(list)
    for file in sorted(Path(directory).iterdir()):
        if file.suffix == '.iso':
            # Remove '_pm' from stem to get the base key
            iso_key = file.stem.replace('_pm', '')
            logging.debug(f"ISO key: {iso_key}")
            # No need to initialize file_map[iso_key], defaultdict handles it
        elif file.suffix == '.mp4':
            logging.debug(f"Processing MP4: {file}")
            stem = file.stem
            if 'f' in stem and 'r' in stem:
                # For multiple MP4s, remove from 'f' onwards
                mp4_key = stem.split('f')[0]
            else:
                # For single MP4s, remove '_sc' suffix
                if stem.endswith('_sc'):
                    mp4_key = stem[:-3]  # Remove '_sc' suffix
                    mp4_key = mp4_key.rstrip('_')  # Remove any trailing underscores
                else:
                    mp4_key = stem
            logging.debug(f"MP4 key: {mp4_key}")
            # Append the MP4 file to the file_map regardless of key existence
            file_map[mp4_key].append(file.name)
    logging.info(f"File map: {dict(file_map)}")
    return file_map

# Fetch the original record
def fetch_original_record(conn, reference_filename):
    curs = conn.cursor()
    try:
        query = 'SELECT * FROM tbl_metadata WHERE "asset.referenceFilename" = ?'
        logging.info(f"Fetching record with asset.referenceFilename = {reference_filename}")
        curs.execute(query, [reference_filename])
        record = curs.fetchone()
        if record:
            columns = [desc[0] for desc in curs.description]
            record_dict = dict(zip(columns, record))
            logging.info("Record fetched successfully.")

            # Fields that should be treated as strings
            fields_as_strings = ['asset.schemaVersion', 'bibliographic.barcode']
            for field in fields_as_strings:
                if field in record_dict and record_dict[field] is not None:
                    record_dict[field] = str(record_dict[field])

            return record_dict
        else:
            logging.error("No record found.")
            return None
    except Exception as e:
        logging.error(f"Error fetching record: {e}")
        return None
    finally:
        curs.close()

# Insert a new record
def insert_new_record(conn, original_record, mp4_file, face_number, region_number):
    curs = conn.cursor()
    try:
        # Set default values if face_number or region_number are None
        if face_number is None:
            face_number = ''  # Or set to a default value like '1' if appropriate
        if region_number is None:
            region_number = ''  # Or set to a default value like '1' if appropriate

        new_record_data = {
            # Copy fields from the original record
            'WorkOrderID': original_record['WorkOrderID'],
            'Archival box barcode': original_record['Archival box barcode'],
            'Archival box number': original_record['Archival box number'],
            'cmsCollectionTitle': original_record['cmsCollectionTitle'],
            'asset.fileRole': 'sc',  # Change to 'sc' for the new record
            'asset.fileExt': 'mp4',  # Change to 'mp4' for the new record
            'asset.schemaVersion': original_record['asset.schemaVersion'],
            'bibliographic.primaryID': original_record['bibliographic.primaryID'],
            'bibliographic.catalogBNumber': original_record['bibliographic.catalogBNumber'],
            'bibliographic.classmark': original_record['bibliographic.classmark'],
            'bibliographic.cmsCollectionID': original_record['bibliographic.cmsCollectionID'],
            'bibliographic.cmsItemID': original_record['bibliographic.cmsItemID'],
            'bibliographic.contentNotes': original_record['bibliographic.contentNotes'],
            'bibliographic.date': original_record['bibliographic.date'],
            'bibliographic.divisionCode': original_record['bibliographic.divisionCode'],
            'bibliographic.formerClassmark': original_record['bibliographic.formerClassmark'],
            'bibliographic.group': original_record['bibliographic.group'],
            'bibliographic.mssID': original_record['bibliographic.mssID'],
            'bibliographic.nonCMSItemID': original_record['bibliographic.nonCMSItemID'],
            'bibliographic.projectCode': original_record['bibliographic.projectCode'],
            'bibliographic.sequence': original_record['bibliographic.sequence'],
            'bibliographic.title': original_record['bibliographic.title'],
            'bibliographic.vernacularDivisionCode': original_record['bibliographic.vernacularDivisionCode'],
            'digitizationProcess.captureSoftware.manufacturer': original_record['digitizationProcess.captureSoftware.manufacturer'],
            'digitizationProcess.captureSoftware.platform': original_record['digitizationProcess.captureSoftware.platform'],
            'digitizationProcess.captureSoftware.productName': original_record['digitizationProcess.captureSoftware.productName'],
            'digitizationProcess.captureSoftware.version': original_record['digitizationProcess.captureSoftware.version'],
            'digitizationProcess.notes.processNotes': original_record['digitizationProcess.notes.processNotes'],
            'digitizationProcess.playbackDevice.model': original_record['digitizationProcess.playbackDevice.model'],
            'digitizationProcess.playbackDevice.manufacturer': original_record['digitizationProcess.playbackDevice.manufacturer'],
            'digitizationProcess.playbackDevice.serialNumber': original_record['digitizationProcess.playbackDevice.serialNumber'],
            'bibliographic.accessNotes': original_record['bibliographic.accessNotes'],
            'bibliographic.barcode': original_record['bibliographic.barcode'],
            'source.physicalDescription.diameter.measure': original_record['source.physicalDescription.diameter.measure'],
            'source.physicalDescription.diameter.unit': original_record['source.physicalDescription.diameter.unit'],
            'source.physicalDescription.dataCapacity.measure': original_record['source.physicalDescription.dataCapacity.measure'],
            'source.physicalDescription.dataCapacity.unit': original_record['source.physicalDescription.dataCapacity.unit'],
            'source.object.type': original_record['source.object.type'],
            'source.object.format': original_record['source.object.format'],
            'source.object.generation': original_record['source.object.generation'],
            'source.object.volumeNumber': int(original_record['source.object.volumeNumber']),
            'source.audioRecording.numberOfAudioTracks': int(original_record['source.audioRecording.numberOfAudioTracks']),
            'source.audioRecording.audioSoundField': original_record['source.audioRecording.audioSoundField'],
            'source.contentSpecifications.broadcastStandard': original_record['source.contentSpecifications.broadcastStandard'],
            'source.contentSpecifications.colorBW': original_record['source.contentSpecifications.colorBW'],
            'source.contentSpecifications.regionCode': original_record['source.contentSpecifications.regionCode'],
            'source.physicalDescription.stockManufacturer': original_record['source.physicalDescription.stockManufacturer'],
            'source.physicalDescription.stockProductID': original_record['source.physicalDescription.stockProductID'],
            'source.physicalDescription.dyeLayer': original_record['source.physicalDescription.dyeLayer'],
            'source.physicalDescription.reflectiveLayer': original_record['source.physicalDescription.reflectiveLayer'],
            'digitizer.operator.firstName': original_record['digitizer.operator.firstName'],
            'digitizer.operator.lastName': original_record['digitizer.operator.lastName'],
            'digitizer.organization.address.city': original_record['digitizer.organization.address.city'],
            'digitizer.organization.address.postalCode': original_record['digitizer.organization.address.postalCode'],
            'digitizer.organization.address.state': original_record['digitizer.organization.address.state'],
            'digitizer.organization.address.street1': original_record['digitizer.organization.address.street1'],
            'digitizer.organization.address.street2': original_record['digitizer.organization.address.street2'],
            'digitizer.organization.name': original_record['digitizer.organization.name'],
            'technical.signalNotes': original_record['technical.signalNotes'],
            # Fields specific to the new record
            'source.subObject.faceNumber': face_number,
            'source.subObject.regionNumber': region_number,
        }

        # Prepare the insert statement
        columns = ', '.join(f'"{col}"' for col in new_record_data.keys())
        placeholders = ', '.join(['?'] * len(new_record_data))
        sql = f"INSERT INTO tbl_metadata ({columns}) VALUES ({placeholders})"
        values = list(new_record_data.values())

        logging.info(f"Inserting new record for file: {mp4_file}")
        logging.debug(f"SQL Statement: {sql}")
        logging.debug(f"Values: {values}")

        curs.execute(sql, values)
        conn.commit()
        logging.info("New record inserted successfully.")
    except Exception as e:
        logging.error(f"Failed to insert new record: {e}")
        conn.rollback()
    finally:
        curs.close()

# Extract face number from filename
def extract_face_number(filename):
    if 'f' in filename and 'r' in filename:
        try:
            return int(filename.split('f')[1].split('r')[0])
        except ValueError:
            logging.warning(f"Could not extract face number from filename: {filename}")
            return None
    return None

# Extract region number from filename
def extract_region_number(filename):
    if 'r' in filename:
        try:
            return int(filename.split('r')[1].split('_')[0])
        except ValueError:
            logging.warning(f"Could not extract region number from filename: {filename}")
            return None
    return None

# Duplicate and modify records
def duplicate_records(conn, file_map):
    for iso_key, mp4_files in file_map.items():
        reference_filename = iso_key + '_pm.iso'
        logging.info(f"Processing ISO file: {reference_filename}")
        original_record = fetch_original_record(conn, reference_filename)
        if not original_record:
            logging.error(f"Original record not found for {reference_filename}. Skipping.")
            continue
        for mp4_file in mp4_files:
            face_number = extract_face_number(mp4_file)
            region_number = extract_region_number(mp4_file)

            if face_number is None and region_number is None:
                logging.info(f"No face or region number found for {mp4_file}. Proceeding without them.")

            # Insert the new record
            insert_new_record(conn, original_record, mp4_file, face_number, region_number)

def main():
    directory = args.directory
    conn = connect_to_database()
    if not conn:
        return
    try:
        file_map = crawl_directory(directory)
        duplicate_records(conn, file_map)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
