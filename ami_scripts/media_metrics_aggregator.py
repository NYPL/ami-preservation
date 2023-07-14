#!/usr/bin/env python3

import pandas as pd
import numpy as np
import argparse
import re
from collections import defaultdict

def analyze_csv(file_path, output_path):
    # Load the CSV file into a DataFrame
    df = pd.read_csv(file_path, low_memory=False)

    # Ensure the specific columns exist
    required_columns = ['source.object.format', 'asset.referenceFilename', 'technical.durationMilli.measure', 'technical.fileSize.measure']
    if not set(required_columns).issubset(df.columns):
        print("Required columns not found in the input CSV.")
        return

    # Convert numeric columns to appropriate dtype
    for column in required_columns[2:]:
        df[column] = pd.to_numeric(df[column], errors='coerce')

    # Extract the base filename to group files from the same physical object together
    df['physical_object'] = df['asset.referenceFilename'].str.extract(r'(^.*?(?=_v))')

    # Sum up the file sizes for files derived from the same physical object
    physical_object_sums = df.groupby('physical_object')['technical.fileSize.measure'].sum()

    # Replace individual file sizes with the sum for the corresponding physical object
    df['technical.fileSize.measure'] = df['physical_object'].map(physical_object_sums)

    # Group by 'source.object.format' and 'physical_object' and calculate averages
    grouped_df = df.groupby(['source.object.format', 'physical_object'])[required_columns[2:]].mean()

    format_averages = defaultdict(lambda: defaultdict(float))
    format_counts = defaultdict(lambda: defaultdict(int))

    # Iterate over the grouped DataFrame
    for (format_type, physical_object), row in grouped_df.iterrows():
        # Keep track of the sum and count for each format type to calculate the overall average later
        format_averages[format_type]['technical.durationMilli.measure'] += row['technical.durationMilli.measure']
        format_averages[format_type]['technical.fileSize.measure'] += row['technical.fileSize.measure']
        format_counts[format_type]['technical.durationMilli.measure'] += 1
        format_counts[format_type]['technical.fileSize.measure'] += 1

    output_data = []

    for format_type, averages in format_averages.items():
        # Calculate the overall average for each format type
        averages['technical.durationMilli.measure'] /= format_counts[format_type]['technical.durationMilli.measure']
        averages['technical.fileSize.measure'] /= format_counts[format_type]['technical.fileSize.measure']

        duration = averages['technical.durationMilli.measure']
        file_size = averages['technical.fileSize.measure']

        # Convert duration to HH:MM:SS format
        hours = duration // 3600000
        minutes = (duration % 3600000) // 60000
        seconds = (duration % 60000) // 1000
        milliseconds = duration % 1000
        duration_str = "{:0>2}:{:0>2}:{:0>2}.{:0>3}".format(int(hours), int(minutes), int(seconds), int(milliseconds))

        # Convert file size to human readable format
        suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        i = 0
        while file_size >= 1024 and i < len(suffixes)-1:
            file_size /= 1024.
            i += 1
        file_size_str = f"{file_size:.2f} {suffixes[i]}"

        # Add data to output_data
        output_data.append([format_type, duration_str, file_size_str])

    # Create a DataFrame from output_data and write it to a CSV file
    output_df = pd.DataFrame(output_data, columns=['Format', 'Average Duration', 'Average File Size'])
    output_df.to_csv(output_path, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze a CSV file.')
    parser.add_argument('-i', '--input', type=str, required=True, help='Path to the input CSV file')
    parser.add_argument('-o', '--output', type=str, required=True, help='Path to the output CSV file')

    args = parser.parse_args()
    analyze_csv(args.input, args.output)
