#!/usr/bin/env python3

import os
import pandas as pd
import json
import argparse
from pathlib import Path

# Argument parser setup
parser = argparse.ArgumentParser(description="Convert a FileMaker merge file to JSON files")
parser.add_argument("-s", "--source", help="The path to the FileMaker merge file", required=True)
parser.add_argument("-d", "--destination", help="The directory to save the JSON files to", required=True)
args = parser.parse_args()

# Example FileMaker merge file
merge_file = args.source

# Load the merge file using pandas
df = pd.read_csv(merge_file, encoding="mac_roman", dtype={
	'digitizationProcess.analogDigitalConverter.serialNumber': object,
	'digitizationProcess.captureSoftware.version': object,
	'digitizationProcess.playbackDevice.serialNumber': object,
	'digitizationProcess.timeBaseCorrector.serialNumber': object,
	'digitizationProcess.phonoPreamp.serialNumber': object,
	'digitizationProcess.playbackDevice.phonoCartridge.stylusSize.measure': object,
	'source.physicalDescription.properties.stockProductID': object,
    'digitizer.organization.address.postalCode': object,
	'source.physicalDescription.edgeCode': object,
    'bibliographic.barcode': object,
    'bibliographic.cmsCollectionID': object,
    'bibliographic.cmsItemID': object,
    'bibliographic.primaryID': object
})

# Drop empty columns and the 'asset.fileExt' column
df = df.dropna(axis=1, how="all")
df = df.drop(['asset.fileExt'], axis=1)

# Set the output directory for JSON files
json_directory = Path(args.destination).resolve()

# Create the output directory if it doesn't exist
json_directory.mkdir(parents=True, exist_ok=True)

def convert_dotKeyToNestedDict(tree: dict, key: str, value: str) -> dict:
    """
    Convert a dot-delimited key and its corresponding value to a nested dictionary.

    Args:
        tree: The dictionary to add the key-value pair to.
        key: The dot-delimited key string.
        value: The value associated with the key.

    Returns:
        The updated dictionary with the key-value pair added.

    Example:
        >>> d = {}
        >>> convert_dotKeyToNestedDict(d, 'a.b.c', 'value')
        {'a': {'b': {'c': 'value'}}}
    """

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


# Iterate through each row in the DataFrame
for (index, row) in df.iterrows():
    nested_dict = {}
    json_tree = row.to_dict()

    # Convert the flat dictionary to a nested dictionary
    for key, value in json_tree.items():
        nested_dict = convert_dotKeyToNestedDict(nested_dict, key, value)

    # Save the nested dictionary as a JSON file
    json_filename = os.path.splitext(row["asset.referenceFilename"])[0] + ".json"
    json_filepath = json_directory.joinpath(json_filename)
    try:
        with json_filepath.open('w') as f:
            json.dump(nested_dict, f, indent=4)
    except IOError as e:
        print(f"Error writing JSON file '{json_filepath}': {e}")
