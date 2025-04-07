#!/usr/bin/env python3
"""
This script reads two CSV files:
  - a vendor CSV (specified by -v or --vendor) that contains a column named
    'bibliographic.cmsCollectionID' and a column 'cmsCollectionTitle'
  - a collections CSV (specified by -c or --collections) with two columns: 'c #' and 'c title'

For each row in the vendor CSV, the script uses the value in 'bibliographic.cmsCollectionID'
to search for a matching key (from the 'c #' column) in the collections CSV.
If a match is found, the script updates the vendor CSV’s 'cmsCollectionTitle'
with the corresponding value from 'c title'.

Usage:
    update_vendor_collection.py -v vendor.csv -c collections.csv -o output.csv
"""

import csv
import argparse
import sys
import chardet

def detect_encoding(file_path, num_bytes=1024):
    """Detect the file encoding by reading a portion of the file."""
    with open(file_path, 'rb') as f:
        rawdata = f.read(num_bytes)
    result = chardet.detect(rawdata)
    return result['encoding']

def determine_delimiter(file_path, encoding):
    """Determine the delimiter by checking the first line of the file."""
    with open(file_path, newline='', encoding=encoding, errors='replace') as f:
        first_line = f.readline()
    if "\t" in first_line:
        return "\t"
    elif "," in first_line:
        return ","
    else:
        # Fallback to comma if no clear delimiter is found.
        return ","

def main():
    parser = argparse.ArgumentParser(
        description="Update vendor CSV with collection titles from collections CSV"
    )
    parser.add_argument("-v", "--vendor", required=True,
                        help="Path to the vendor CSV file")
    parser.add_argument("-c", "--collections", required=True,
                        help="Path to the collections CSV file")
    parser.add_argument("-o", "--output", required=True,
                        help="Path for the output CSV file")
    args = parser.parse_args()

    # Process collections CSV
    collections_encoding = detect_encoding(args.collections)
    print(f"Detected encoding for collections CSV: {collections_encoding}")
    collections_delimiter = determine_delimiter(args.collections, collections_encoding)
    print(f"Using delimiter '{collections_delimiter}' for collections CSV")
    
    collections_map = {}
    try:
        with open(args.collections, newline='', encoding=collections_encoding, errors='replace') as coll_file:
            reader = csv.DictReader(coll_file, delimiter=collections_delimiter)
            print(f"Detected header columns in collections CSV: {reader.fieldnames}")
            for row in reader:
                # Normalize keys in case there is extra whitespace
                row = {k.strip(): v for k, v in row.items()}
                if "c #" in row and "c title" in row:
                    key = row["c #"].strip()
                    value = row["c title"].strip()
                    collections_map[key] = value
                else:
                    print("Warning: Unexpected header format in collections CSV.", file=sys.stderr)
    except Exception as e:
        print(f"Error reading collections CSV: {e}", file=sys.stderr)
        sys.exit(1)

    # Process vendor CSV
    vendor_encoding = detect_encoding(args.vendor)
    print(f"Detected encoding for vendor CSV: {vendor_encoding}")
    vendor_delimiter = determine_delimiter(args.vendor, vendor_encoding)
    print(f"Using delimiter '{vendor_delimiter}' for vendor CSV")
    
    updated_rows = []
    try:
        with open(args.vendor, newline='', encoding=vendor_encoding, errors='replace') as vendor_file:
            reader = csv.DictReader(vendor_file, delimiter=vendor_delimiter)
            # Normalize header names by stripping whitespace
            if reader.fieldnames is not None:
                reader.fieldnames = [field.strip() for field in reader.fieldnames]
            fieldnames = reader.fieldnames
            print("Vendor CSV headers:", fieldnames)
            if fieldnames is None or "cmsCollectionTitle" not in fieldnames:
                print("Error: 'cmsCollectionTitle' column not found in vendor CSV.", file=sys.stderr)
                sys.exit(1)
            for row in reader:
                # Strip whitespace from keys in the row
                row = {k.strip(): v for k, v in row.items()}
                cms_collection_id = row["bibliographic.cmsCollectionID"].strip()
                # If a matching collection is found, update the cmsCollectionTitle.
                if cms_collection_id in collections_map:
                    row["cmsCollectionTitle"] = collections_map[cms_collection_id]
                updated_rows.append(row)
    except Exception as e:
        print(f"Error reading vendor CSV: {e}", file=sys.stderr)
        sys.exit(1)

    # Write the updated vendor CSV to the output file using the detected vendor CSV delimiter.
    try:
        with open(args.output, 'w', newline='', encoding=vendor_encoding, errors='replace') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=vendor_delimiter)
            writer.writeheader()
            writer.writerows(updated_rows)
    except Exception as e:
        print(f"Error writing output CSV: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
