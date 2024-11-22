#!/usr/bin/env python3

import csv
import argparse

def extract_unique_ids_from_bucket(bucket_csv):
    """Extracts unique 6-digit IDs from the bucket CSV."""
    unique_ids = set()
    with open(bucket_csv, 'r') as file:
        reader = csv.reader(file, delimiter='\t')  # Tab-delimited
        for row_num, row in enumerate(reader, start=1):
            try:
                # Extract the key (1st column) and split to get the 6-digit ID
                key = row[0]
                id_part = key.split('_')[1]  # Assuming format like axv_211010_v01_sc.json
                if id_part.isdigit() and len(id_part) == 6:
                    unique_ids.add(id_part)
            except IndexError:
                print(f"Skipping malformed row {row_num}: {row}")
            except Exception as e:
                print(f"Error processing row {row_num}: {row}. Error: {e}")
    return unique_ids

def find_ids_with_issues(bucket_ids, streaming_csv):
    """Finds IDs present in the bucket but marked as FALSE in the streaming CSV."""
    issues = []
    with open(streaming_csv, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            idf = row['item_idf']
            media_available = row['media_available']
            if idf in bucket_ids and media_available.upper() == 'FALSE':
                issues.append(idf)
    return issues

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Compare AWS bucket and streaming platform lists.")
    parser.add_argument('-b', '--bucket', required=True, help="Path to the AWS bucket CSV file")
    parser.add_argument('-s', '--streaming', required=True, help="Path to the streaming platform CSV file")
    parser.add_argument('-o', '--output', help="Output file to save the results", default='issues.txt')
    args = parser.parse_args()

    # Extract IDs from bucket CSV
    print("Extracting unique IDs from the bucket CSV...")
    bucket_ids = extract_unique_ids_from_bucket(args.bucket)
    print(f"Found {len(bucket_ids)} unique IDs in the bucket.")

    # Compare with streaming platform CSV
    print("Comparing IDs with the streaming platform list...")
    issues = find_ids_with_issues(bucket_ids, args.streaming)
    print(f"Found {len(issues)} IDs with issues.")

    # Save results
    if issues:
        with open(args.output, 'w') as file:
            for issue in issues:
                file.write(f"{issue}\n")
        print(f"Issues saved to {args.output}")
    else:
        print("No issues found.")

if __name__ == '__main__':
    main()
