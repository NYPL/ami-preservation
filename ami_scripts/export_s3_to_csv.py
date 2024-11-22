#!/usr/bin/env python3

import boto3
import csv
import argparse

def list_s3_objects(bucket_name, output_file):
    # Initialize S3 client
    s3 = boto3.client('s3')

    try:
        # Write to CSV
        with open(output_file, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Key', 'LastModified', 'Size'])  # CSV header

            # Pagination logic
            continuation_token = None
            total_files = 0

            while True:
                if continuation_token:
                    response = s3.list_objects_v2(Bucket=bucket_name, ContinuationToken=continuation_token)
                else:
                    response = s3.list_objects_v2(Bucket=bucket_name)

                # Write object details to CSV
                for obj in response.get('Contents', []):
                    writer.writerow([obj['Key'], obj['LastModified'], obj['Size']])
                    total_files += 1

                # Check if there are more objects to fetch
                if response.get('IsTruncated'):  # True if there are more objects to fetch
                    continuation_token = response.get('NextContinuationToken')
                else:
                    break

        print(f"Export complete! {total_files} files written to {output_file}")

    except Exception as e:
        print(f"Error: {e}")

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Export contents of an S3 bucket to a CSV file.")
    parser.add_argument('-b', '--bucket', required=True, help="Name of the S3 bucket")
    parser.add_argument('-o', '--out', required=True, help="Output CSV file location and name")
    args = parser.parse_args()

    # Call the function to list S3 objects
    list_s3_objects(args.bucket, args.out)

if __name__ == '__main__':
    main()
