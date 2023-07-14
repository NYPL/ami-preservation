#!/usr/bin/env python3
import pandas as pd
import os
import json
import argparse
from pandas import json_normalize  # for flattening the json file
from pathlib import Path
from multiprocessing import Pool, cpu_count

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--source', required=True, help='Source directory containing JSON files')
    parser.add_argument('-d', '--destination', required=True, help='Destination CSV file')
    return parser.parse_args()

def read_json(file):
    try:
        with open(file, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)

        # Normalize and flatten the json
        df = pd.json_normalize(data)

        return df
    except json.JSONDecodeError:
        print(f"Could not decode JSON from file: {file}")
        return pd.DataFrame()  # return empty DataFrame for problematic files


def main():
    args = parse_args()
    source_dir = Path(args.source)
    destination_file = Path(args.destination)

    json_files = list(source_dir.rglob('*.json'))

    # Use a Pool of processes to read the JSON files into DataFrames
    with Pool(processes=cpu_count()) as pool:
        df_list = pool.map(read_json, json_files)

    # Concatenate all dataframes into one
    df = pd.concat(df_list, ignore_index=True)

    # Write the dataframe to a csv file
    df.to_csv(destination_file, index=False)

if __name__ == "__main__":
    main()
