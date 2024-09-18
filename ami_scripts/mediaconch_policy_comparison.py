#!/usr/bin/env python3

import os
import argparse
import xml.etree.ElementTree as ET
import pandas as pd
from openpyxl import load_workbook

def parse_policy(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    policy_rules = {}

    for rule in root.findall(".//rule"):
        rule_name = rule.get('name')
        rule_operator = rule.get('operator')  # Get the operator
        rule_value = rule.text if rule.text else ""  # Get the text (rule value)

        # Special handling for rules with the 'must not exist' operator or empty text values
        if rule_operator == "must not exist":
            policy_rules[rule_name] = f"{rule_operator}"  # Store the operator as the value for this rule
        else:
            policy_rules[rule_name] = rule_value

    return policy_rules

def process_directory(directory):
    policies_data = []
    policies_names = []

    # Loop through all XML files in the directory
    for filename in os.listdir(directory):
        if filename.endswith(".xml"):
            file_path = os.path.join(directory, filename)
            print(f"Processing {file_path}...")
            rules = parse_policy(file_path)
            policies_data.append(rules)
            policies_names.append(os.path.basename(file_path))
    
    return policies_names, policies_data

def generate_comparison_dataframe(policies_names, policies_data):
    # Create a DataFrame with the rules as columns and policies as rows
    df = pd.DataFrame(policies_data, index=policies_names)

    # Replace missing values with a custom placeholder
    df = df.fillna("Rule not in policy")

    return df

def adjust_column_width(excel_writer, df):
    workbook = excel_writer.book
    worksheet = excel_writer.sheets['Sheet1']

    # Adjust column width based on max length of column header and cell values
    for idx, col in enumerate(df.columns, 1):  # Start enumeration at 1 for correct Excel column indexing
        max_len = max(
            df[col].astype(str).apply(len).max(),  # Max length in column
            len(col)  # Length of column header
        ) + 4  # Adding extra space for readability
        worksheet.column_dimensions[chr(64 + idx)].width = max_len

def main():
    parser = argparse.ArgumentParser(
        description="Compare MediaConch policies by extracting rules and values across policies."
    )
    parser.add_argument(
        "-d", "--directory", required=True, help="Directory containing XML files"
    )
    parser.add_argument(
        "-o", "--output", required=True, help="Output file (CSV or Excel format)"
    )
    args = parser.parse_args()

    policies_names, policies_data = process_directory(args.directory)

    # Create DataFrame for comparison
    df = generate_comparison_dataframe(policies_names, policies_data)

    # Output to CSV or Excel
    if args.output.endswith('.csv'):
        df.to_csv(args.output)
    elif args.output.endswith('.xlsx'):
        with pd.ExcelWriter(args.output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Sheet1')
            adjust_column_width(writer, df)
    else:
        print("Unsupported output format. Please use .csv or .xlsx.")

    print(f"Comparison saved to {args.output}")

if __name__ == "__main__":
    main()
