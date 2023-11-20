#!/usr/bin/env python3

import argparse
import pandas as pd
import chardet

# Define and parse command line arguments
parser = argparse.ArgumentParser(description='Process a CSV file.')
parser.add_argument('-s', '--source', required=True, help='source CSV file')
parser.add_argument('-d', '--destination', required=True, help='destination Excel file')
args = parser.parse_args()

# Function to guess the encoding of a file
def guess_encoding(file):
    with open(file, 'rb') as f:
        result = chardet.detect(f.read())
    return result['encoding']

# 1) Read the csv into a dataframe
encoding = guess_encoding(args.source)
df = pd.read_csv(args.source, encoding=encoding, dtype={'id_barcode': str, 'id_barcode.1': str})

# Strip leading/trailing white space from 'name_d_calc', 'id_barcode.1', 'ux_loc_active_d'
df['name_d_calc'] = df['name_d_calc'].str.strip()
df['id_barcode.1'] = df['id_barcode.1'].apply(str).str.strip()
df['ux_loc_active_d'] = df['ux_loc_active_d'].str.strip()

# 2) Export the dataframe to Excel with 2 sheets

# Create a Pandas Excel writer using XlsxWriter as the engine.
writer = pd.ExcelWriter(args.destination, engine='xlsxwriter')

# Write the original dataframe to the first sheet
df.to_excel(writer, sheet_name='Original CSV', index=False)

# Create a summary dataframe for the top of the second sheet
summary_df = pd.DataFrame()

# Calculate the total number of objects (assuming 'ref_ami_id' uniquely identifies objects)
summary_df.loc[0, 'Total number of objects'] = df['ref_ami_id'].nunique()

# Count the unique boxes
summary_df.loc[1, 'Count of unique boxes'] = df['name_d_calc'].nunique()

# Breakdown by format
format_counts = df['format_3'].value_counts().reset_index()
format_counts.columns = ['Format', 'Count']
format_counts[' '] = ''  # To create an empty column for better readability

# Write the summary dataframe and format_counts to the second sheet
summary_df.to_excel(writer, sheet_name='Summary', index=False, startrow=0)
format_counts.to_excel(writer, sheet_name='Summary', index=False, startrow=len(summary_df)+2)

# Create a dataframe for the box-related information
box_df = df[['name_d_calc', 'id_barcode.1', 'ux_loc_active_d']]

# Drop duplicates from box_df
box_df = box_df.drop_duplicates()

# Group by 'name_d_calc' and see how many unique 'id_barcode.1' are associated with each box
barcode_counts_per_box = box_df.groupby('name_d_calc')['id_barcode.1'].nunique()

# Join the unique barcode count to the box_df
box_df.set_index('name_d_calc', inplace=True)
box_df = box_df.join(barcode_counts_per_box, rsuffix='_unique_count')

# Reset the index of box_df
box_df.reset_index(inplace=True)

# Write the box dataframe to the second sheet, below the format_counts dataframe
box_df.to_excel(writer, sheet_name='Summary', index=False, header=True, startrow=len(summary_df)+len(format_counts)+4)

# Close the Pandas Excel writer and output the Excel file
writer.close()
