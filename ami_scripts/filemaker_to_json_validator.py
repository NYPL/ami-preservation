#!/usr/bin/env python3

import os
import pandas as pd
import json
import argparse
import subprocess
from pathlib import Path
from collections import Counter
import glob
import numpy as np

ZERO_VALUE_FIELDS = ['source.audioRecording.numberOfAudioTracks', 'source.physicalDescription.conditionfading',
                     'source.physicalDescription.conditionscratches', 'source.physicalDescription.conditionsplices',
                     'source.physicalDescription.conditionperforationdamage', 'source.physicalDescription.conditiondistortion',
                     'source.physicalDescription.shrinkage.measure', 'source.physicalDescription.acetateDecayLevel']

# Define the convert_mixed_types function
def convert_mixed_types(value):
    """
    Convert value to a float or integer if possible, otherwise return the original string.
    Preserve fractional numbers by converting to float and convert to integer only if the number is whole.
    """
    try:
        float_value = float(value)
        # If the float value is equivalent to an int, return it as int to avoid unnecessary decimal points.
        if float_value.is_integer():
            return int(float_value)
        else:
            return float_value
    except ValueError:
        return value

def get_info(source_directory, metadata_directory):
    source_path = Path(source_directory)
    json_list = list(source_path.glob('**/*.json'))
    json_list.sort()

    print(f'\nNow Counting JSON files by Type:\n')
    types = []
    for file in json_list:
        with file.open('r') as jsonFile:
            data = json.load(jsonFile)
            types.append(data['source']['object']['type'])
    print(Counter(types))
    print('\n')
    print(f'Now Validating JSON files:\n')

    schema_directory = Path(metadata_directory, 'versions/2.0/schema')

    valid_count = 0
    invalid_count = 0

    for file in json_list:
        with file.open('r') as jsonFile:
            data = json.load(jsonFile)
            ajv_command = get_ajv_command(data, str(file))
            result = subprocess.run(ajv_command, cwd=schema_directory)

            if result.returncode == 0:
                valid_count += 1
            else:
                invalid_count += 1

    print(f"\nTotal valid JSON files: {valid_count}")
    print(f"Total invalid JSON files: {invalid_count}")


def get_ajv_command(data, file):
    object_type = data['source']['object']['type']
    object_format = data['source']['object']['format']

    schema_mapping = {
        'video cassette analog': 'digitized_videocassetteanalog.json',
        'video cassette digital': 'digitized_videocassettedigital.json',
        'video reel': 'digitized_videoreel.json',
        'video optical disc': 'digitized_videoopticaldisc.json',
        'audio cassette analog': 'digitized_audiocassetteanalog.json',
        'audio reel analog': 'digitized_audioreelanalog.json',
        'audio cassette digital': 'digitized_audiocassettedigital.json',
        'audio reel digital': 'digitized_audioreeldigital.json',
        'audio optical disc': 'digitized_audioopticaldisc.json',
        'audio grooved disc': 'digitized_audiogrooveddisc.json',
        'audio grooved cylinder': 'digitized_audiogroovedcylinder.json',
        'audio magnetic wire': 'digitized_audiomagneticwire.json',
        'data optical disc': 'digitized_dataopticaldisc.json',
    }

    film_formats = ('8mm film, silent', '8mm film, optical sound',
                    '8mm film, magnetic sound', 'Super 8 film, silent',
                    'Super 8 film, optical sound', 'Super 8 film, magnetic sound',
                    '16mm film, silent', '16mm film, optical sound', '16mm film, magnetic sound',
                    '35mm film, silent', '35mm film, optical sound', '35mm film, magnetic sound',
                    '9.5mm film, silent', 'Double 8mm film, silent')

    audio_film_formats = ('16mm film, optical track', '16mm film, full-coat magnetic sound',
                          '35mm film, optical track', '35mm film, full-coat magnetic sound')

    if object_type in schema_mapping:
        schema_file = schema_mapping[object_type]
    elif object_format in film_formats:
        schema_file = 'digitized_motionpicturefilm.json'
    elif object_format in audio_film_formats:
        schema_file = 'digitized_audiofilm.json'
    else:
        raise ValueError(f"Unknown object type or format: {object_type}, {object_format}")

    ajv_command = [
        'ajv',
        'validate',
        '-s',
        f'../schema/{schema_file}',
        '-r',
        '../schema/fields.json',
        '-d', file,
        '--all-errors',
        '--errors=json'
    ]
    return ajv_command

def convert_dotKeyToNestedDict(tree: dict, key: str, value) -> dict:
    """
    Convert a dot-delimited key and its corresponding value to a nested dictionary, excluding keys with empty values.
    Args:
        tree: The dictionary to add the key-value pair to.
        key: The dot-delimited key string.
        value: The value associated with the key.
    Returns:
        The updated dictionary with the key-value pair added, excluding keys with empty values.
    """
    # If the value is an empty string or NaN, return the tree without adding the key
    if pd.isna(value) or value == "":
        return tree

    if "." in key:
        # Split the key by the first dot and recursively call the function
        # on the first part of the key with the rest of the key and the value
        # as arguments.
        first_key, remaining_keys = key.split(".", 1)
        if first_key not in tree:
            tree[first_key] = {}
        convert_dotKeyToNestedDict(tree[first_key], remaining_keys, value)
    else:
        # Base case: add the key-value pair to the dictionary.
        tree[key] = value

    return tree

def main():
    # Argument parser setup
    parser = argparse.ArgumentParser(description="Convert a FileMaker merge file to JSON files and validate them against JSON schema files")
    parser.add_argument("-i", "--input", help="The path to the input FileMaker merge file", required=True)
    parser.add_argument("-o", "--output", help="The output directory to save the JSON files to", required=True)
    parser.add_argument("-m", "--metadata", help="Path to the directory of JSON schema files", required=True)
    args = parser.parse_args()

    merge_file = args.input
    print(f"\nCreating JSON files from MER file: {merge_file}")


    # Load the merge file using pandas
    df = pd.read_csv(merge_file, encoding="mac_roman", dtype={
        'digitizationProcess.analogDigitalConverter.serialNumber': object,
        'digitizationProcess.captureSoftware.version': object,
        'digitizationProcess.playbackDevice.serialNumber': object,
        'digitizationProcess.timeBaseCorrector.serialNumber': object,
        'digitizationProcess.phonoPreamp.serialNumber': object,
        'digitizationProcess.playbackDevice.phonoCartridge.stylusSize.measure': object,
        'digitizationProcess.playbackDevice.phonoCartridge.model': object,
        'source.physicalDescription.stockProductID': object,
        'digitizer.organization.address.postalCode': object,
        'source.physicalDescription.edgeCode': object,
        'bibliographic.primaryID': object,
        'bibliographic.barcode': object,
        'bibliographic.divisionCode': object,
        'bibliographic.vernacularDivisionCode': object,
        'bibliographic.projectCode': object,
        'bibliographic.cmsCollectionID': object,
        'bibliographic.title': object,
        'bibliographic.date': object,
        'bibliographic.cmsItemID': object,
        'bibliographic.classmark': object,
        'bibliographic.formerClassmark': object,
        'bibliographic.nonCMSItemID': object,
        'bibliographic.catalogBNumber': object,
        'bibliographic.mssID': object,
        'bibliographic.group': object,
        'bibliographic.sequence': object
    })

    # Drop empty columns and the 'asset.fileExt' column
    df = df.dropna(axis=1, how="all")

    # Apply the function to the 'source.physicalDescription.dataCapacity.measure' column
    column_name = 'source.physicalDescription.dataCapacity.measure'
    if column_name in df.columns:
        df[column_name] = df[column_name].apply(convert_mixed_types)

    # Fill NaN values with an empty string for fields not in ZERO_VALUE_FIELDS
    for column in df.columns:
        if column not in ZERO_VALUE_FIELDS:
            df[column] = df[column].fillna("")
    df = df.drop(['asset.fileExt'], axis=1)
    
    # Set the output directory for JSON files
    json_directory = Path(args.output).resolve()

    # Create the output directory if it doesn't exist
    json_directory.mkdir(parents=True, exist_ok=True)
    json_count = 0  # Add a counter to keep track of the number of JSON files created


    # Iterate through each row in the DataFrame
    for (index, row) in df.iterrows():
        nested_dict = {}
        json_tree = row.to_dict()

        for key, value in json_tree.items():
            # Skip null values unless the field is in ZERO_VALUE_FIELDS
            if pd.isnull(value) and key not in ZERO_VALUE_FIELDS:
                continue

            # Convert Timestamp to a string in the format 'YYYY-MM-DD'
            if type(value) == pd.Timestamp:
                value = value.strftime('%Y-%m-%d')

            # Convert numpy generic types to native Python types
            if isinstance(value, np.generic):
                value = np.asscalar(value)

            # Convert the flat dictionary to a nested dictionary
            nested_dict = convert_dotKeyToNestedDict(nested_dict, key, value)

        # Save the nested dictionary as a JSON file
        json_filename = os.path.splitext(row["asset.referenceFilename"])[0] + ".json"
        json_filepath = json_directory.joinpath(json_filename)
        try:
            with json_filepath.open('w') as f:
                json.dump(nested_dict, f, indent=4)
        except IOError as e:
            print(f"Error writing JSON file '{json_filepath}': {e}")
        json_count += 1

    print(f"\n{json_count} Total JSON files created from MER file: {merge_file}")


    output_directory = args.output
    metadata_directory = args.metadata
    get_info(output_directory, metadata_directory)

if __name__ == "__main__":
    main()
