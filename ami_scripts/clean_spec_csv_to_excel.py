#!/usr/bin/env python3

import requests
import argparse
import os
import json
import pandas as pd
import re
import chardet


def get_args():
    parser = argparse.ArgumentParser(description='Prep SPEC CSV for Import into AMIDB')
    parser.add_argument('-s', '--source',
                        help='path to the source XLSX', required=True)
    parser.add_argument('-w', '--workorder',
                        help='Work Order ID to apply to new XLSX', required=False)
    parser.add_argument('-p', '--projectcode',
                    help='Project Code to apply to new XLSX', required=True)
    parser.add_argument('-d', '--destination',
                        help='path to the output directory', required=False)
    parser.add_argument('-c', '--config',
                        help='path to the config file', default='config.json', required=False)
    parser.add_argument('-v', '--vendor',
                        help='Use vendor mode (skips certain cleanup steps and uses default Excel writer)',
                        action='store_true') 
    parser.add_argument('-t', '--trello', help='Create a Trello card for each unique Archival Box Barcode', action='store_true')
    parser.add_argument('--single-card', help='Create a single Trello card for the batch', action='store_true')



    args = parser.parse_args()
    return args

def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        return chardet.detect(file.read())['encoding']

def determine_type_format(row):
    audio_film_formats = [
        "16mm film, optical track",
        "16mm film, full-coat magnetic sound",
        "35mm film, optical track",
        "35mm film, full-coat magnetic sound"
    ]

    format_lower = row['format_1'].lower()
    if format_lower == 'video':
        return row['format_2'], row['format_3'], ''  # Empty string for video
    elif format_lower == 'sound recording':
        return row['format_2'], row['format_3'], '1'  # 1 for sound recordings
    elif format_lower == 'film':
        # Check format_2 for specific audio film formats
        if row['format_2'] in audio_film_formats:
            return row['format_1'], row['format_2'], '1'
        else:
            return row['format_1'], row['format_2'], ''  # Empty string for other formats
    else:
        return None, None, ''
    

def map_division_code(vernacular_code):
    mapping = {
        'SCL': 'scb',
        'DAN': 'myd',
        'RHA': 'myh',
        'MUS': 'mym',
        'TOFT': 'myt',
        'THE': 'myt',
        'MSS': 'mao',
        'GRD': 'grd',
        'NYPLarch': 'axv',
        'MUL': 'mul',
        'BRG': 'mae',
        'JWS': 'maf',
        'LPA': 'myr'

    }
    return mapping.get(vernacular_code, '')  # Return empty string if no match


def map_csv_columns(df):

    # Standard column mappings
    column_mapping = {
        'ref_ami_id': 'bibliographic.primaryID',
        'id_label_text': 'bibliographic.title',
        'id.classmark': 'bibliographic.classmark',
        'bnumber': 'bibliographic.catalogBNumber',
        'id.legacy': 'bibliographic.formerClassmark',
        'division': 'bibliographic.vernacularDivisionCode',
        'ref_collection_id': 'bibliographic.cmsCollectionID',
        'name_d_calc': 'Archival box number',
        'date': 'bibliographic.date',
        'group': 'bibliographic.group',
        'sequence': 'bibliographic.sequence',
        'notes.content': 'bibliographic.contentNotes',
        'notes.preservation': 'source.notes.physicalConditionPreShipNotes',
        'notes': 'bibliographic.accessNotes',
        'manufacturer': 'source.physicalDescription.stockManufacturer',
        'shrinkage': 'source.physicalDescription.shrinkage.measure',
        'basematerial': 'source.physicalDescription.baseMaterial',
        'acetate_decay_level': 'source.physicalDescription.acetateDecayLevel',
        'colorbw': 'source.contentSpecifications.colorBW',
        'edgecode': 'source.physicalDescription.edgeCode',
        'film_element': 'source.object.filmElement',
        'condition_fading': 'source.physicalDescription.conditionfading',
        'condition_scratches': 'source.physicalDescription.conditionscratches',
        'condition_splices': 'source.physicalDescription.conditionsplices',
        'condition_perforation_damage': 'source.physicalDescription.conditionperforationdamage',
        'condition_distortion': 'source.physicalDescription.conditiondistortion',
        'fps': 'source.contentSpecifications.frameRate.measure',
        'generation': 'source.object.generation',
        'length_ft': 'source.physicalDescription.length.measure',
        'emulsion_position': 'source.physicalDescription.emulsionPosition',
        'aspect_ratio': 'source.contentSpecifications.displayAspectRatio',
        'diameter': 'source.physicalDescription.diameter.measure'
    }

    # Check context for the id_barcode column and map accordingly
    barcode_columns = df.filter(like='id_barcode').columns
    for col in barcode_columns:
        barcode_index = df.columns.get_loc(col)
        if df.columns[barcode_index - 1] == 'ref_ami_id':
            # id_barcode next to ref_ami_id refers to item
            column_mapping[col] = 'bibliographic.barcode'
        elif df.columns[barcode_index - 1] == 'name_d_calc':
            # id_barcode next to name_d_calc refers to archival box
            column_mapping[col] = 'Archival box barcode'


    # Apply the function to determine type, format, and faceNumber
    df['source.object.type'], df['source.object.format'], df['source.subObject.faceNumber'] = zip(*df.apply(determine_type_format, axis=1))

    # Drop the original format columns as they are no longer needed
    df.drop(['format_1', 'format_2', 'format_3'], axis=1, inplace=True)

    # Rename columns based on mapping
    df.rename(columns=column_mapping, inplace=True)

    # Map vernacularDivisionCode to divisionCode
    df['bibliographic.divisionCode'] = df['bibliographic.vernacularDivisionCode'].apply(map_division_code)

    # Drop unneeded columns
    unneeded_columns = ['_account.entered', '_dtentered', 'cat_item_record_id',
                        'ref_acq_id', 'title', 'ux_loc_active_d', 'desc.catY', 
                        'cm.trans.type', 'cm.trans.dont', 'cm.de.recY', 
                        'cm.de.rationale', 'time', 'condition_average',
                        '_inspected_y', '_inspected_by', '_inspected_dt', 
                        '_inspected_time', 'batch.status', 'migration_status']
    df.drop(unneeded_columns, axis=1, inplace=True)

    df['asset.schemaVersion'] = '2.0.0'
    df['asset.fileRole'] = 'pm'
    df['source.object.volumeNumber'] = 1

    return df


def read_config(config_path):
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config


def replace_characters(df, replacements):
    for column in df:
        for replacement in replacements:
            old_char = replacement['find']
            new_char = replacement['replace']
            df[column] = df[column].apply(lambda x: re.sub(old_char, new_char, x) if isinstance(x, str) else x)


def apply_format_fixes(df, format_fixes):
    for target_type, formats in format_fixes.items():
        for fmt in formats:
            df.loc[df['source.object.format'] == fmt, 'source.object.type'] = target_type


def get_box_barcode(row, df):
    """
    Function to get the correct 'id_barcode' based on its proximity to 'name_d_calc'.
    """
    # Placeholder for barcode value
    barcode_value = None
    
    # Iterate through each 'id_barcode' column and check its context
    for col in df.filter(like='id_barcode').columns:
        barcode_index = df.columns.get_loc(col)
        # Check if the previous column is 'name_d_calc'
        if df.columns[barcode_index - 1] == 'name_d_calc':
            barcode_value = row[col]
            break  # Stop after finding the first matching barcode
    
    return barcode_value


def categorize_and_create_trello_cards(df, single_card=False):
    api_key = os.getenv('TRELLO_API_KEY')
    token = os.getenv('TRELLO_TOKEN')
    list_ids = {
        'Audio': os.getenv('TRELLO_AUDIO_LIST_ID'),
        'Video': os.getenv('TRELLO_VIDEO_LIST_ID'),
        'Film': os.getenv('TRELLO_FILM_LIST_ID')
    }

    categories = {'Audio': [], 'Video': [], 'Film': []}
    
    # Initialize a variable to hold the work order ID, assuming it's consistent across the batch
    work_order_id = ""

    for index, row in df.iterrows():
        barcode = get_box_barcode(row, df)
        if barcode:
            barcode = str(barcode).strip()
            format_category = row['format_1'].lower()
            if 'sound recording' in format_category:
                category = 'Audio'
            elif 'video' in format_category:
                category = 'Video'
            elif 'film' in format_category:
                category = 'Film'
            else:
                continue

            if barcode not in categories[category]:
                categories[category].append(barcode)
                if not work_order_id:  # Only set the work order ID if it hasn't been set yet
                    work_order_id = str(row.get('WorkOrderId', '')).strip()

    if single_card and work_order_id:
        # Determine the majority category
        majority_category = max(categories, key=lambda cat: len(categories[cat]))
        # Use just the Work Order ID as the card name for single card mode
        card_name = work_order_id
        card_desc = f"Batch processing for {work_order_id}. Includes items from {majority_category} category."
        create_card(api_key, token, list_ids[majority_category], card_name, card_desc)
    else:
        for category, barcodes in categories.items():
            for barcode in barcodes:
                # Use WorkOrderId_Barcode format for the card name in standard mode
                card_name = f"{work_order_id}_{barcode}" if work_order_id else barcode
                create_card(api_key, token, list_ids[category], card_name)

    # Print out the categorized barcodes with counts for verification
    for category, barcodes in categories.items():
        print(f"{len(barcodes)} {category} Barcodes: {', '.join(barcodes)}")




def create_card(api_key, token, list_id, card_name, card_desc=""):
    """Create a card in a specified Trello list"""
    url = "https://api.trello.com/1/cards"
    query = {
        'key': api_key,
        'token': token,
        'idList': list_id,
        'name': card_name,
        'desc': card_desc
    }
    response = requests.post(url, params=query)
    if response.status_code == 200:
        print(f"Card '{card_name}' created successfully!")
    else:
        print(f"Failed to create card. Status code: {response.status_code}, Response: {response.text}")


def cleanup_csv(args):
    if args.source:
        csv_name = os.path.basename(args.source)
        clean_name = os.path.splitext(csv_name)[0] + '_CLEAN.xlsx'

        # Detect file encoding
        file_encoding = detect_encoding(args.source)

        df = pd.read_csv(args.source, encoding=file_encoding)
        
        if args.workorder:
            df['WorkOrderId'] = args.workorder

        if args.trello:
            categorize_and_create_trello_cards(df, single_card=args.single_card)

        df = map_csv_columns(df)
        config = read_config(args.config)
        replace_characters(df, config['replacements'])
        apply_format_fixes(df, config['format_fixes'])

        # Assign the project code to all rows in the new column
        df['bibliographic.projectCode'] = args.projectcode

        # Sort the DataFrame by 'bibliographic.primaryID'
        df.sort_values(by='bibliographic.primaryID', inplace=True)

        if args.vendor:
            # Convert to string and format for filename construction
            temp_volume_number = 'v0' + df['source.object.volumeNumber'].astype(str)
            temp_face_number = df['source.subObject.faceNumber'].fillna('')
            temp_face_number = temp_face_number.apply(lambda x: 'f' + str(x).zfill(2) if x else '')

            # Concatenate to create 'Filename (reference)' column
            df['Filename (reference)'] = df['bibliographic.divisionCode'].astype(str) + '_' + \
                                        df['bibliographic.primaryID'].astype(str) + '_' + \
                                        temp_volume_number + \
                                        temp_face_number + '_' + \
                                        df['asset.fileRole'].astype(str)

        
        # Now sort the columns alphabetically
        df = df.reindex(sorted(df.columns), axis=1)
        # Reset the index to get a clean sequential index
        df.reset_index(drop=True, inplace=True)
        
        if args.destination:
            if os.path.exists(args.destination):
                output_file_path = os.path.join(args.destination, clean_name)
                if args.vendor:  
                    df.to_excel(output_file_path, sheet_name='Sheet1', index=False)  
                else: 
                    writer = pd.ExcelWriter(output_file_path, engine='xlsxwriter')
                    df.to_excel(writer, sheet_name='Sheet1')
                    writer.close()
        

def main():
    arguments = get_args()
    cleanup_csv(arguments)

if __name__ == '__main__':
    main()
    exit(0)


