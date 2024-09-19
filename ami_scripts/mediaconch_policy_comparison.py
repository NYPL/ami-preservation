#!/usr/bin/env python3

import os
import argparse
import xml.etree.ElementTree as ET
import pandas as pd
import re
import plotly.express as px

def sanitize_column_name(name):
    """ Replace invalid characters for Excel column names. """
    return re.sub(r'[^A-Za-z0-9_]', '_', name)

def parse_policy(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    policy_rules = {}

    for rule in root.findall(".//rule"):
        rule_name = rule.get('name')
        rule_operator = rule.get('operator')  # Get the operator
        rule_value = rule.text if rule.text else ""  # Get the text (rule value)

        # Special handling for rules with the 'exists' operator or empty text values
        if rule_operator == "exists":
            policy_rules[rule_name] = "exists"
        elif rule_operator == "must not exist":
            policy_rules[rule_name] = "must not exist"
        else:
            # If rule has a value, store it. Otherwise, use the operator as the value.
            policy_rules[rule_name] = rule_value if rule_value else rule_operator

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

    # Sanitize column names to remove invalid characters for Excel
    df.columns = [sanitize_column_name(col) for col in df.columns]

    return df

def adjust_column_width(excel_writer, df):
    worksheet = excel_writer.sheets['Sheet1']

    # Adjust column width based on max length of column header and cell values
    for idx, col in enumerate(df.columns, 1):  # Start enumeration at 1 for correct Excel column indexing
        max_len = max(
            df[col].astype(str).apply(len).max(),  # Max length in column
            len(col)  # Length of column header
        ) + 2  # Adding extra space for readability

        column_letter = worksheet.cell(1, idx).column_letter  # Get the column letter
        worksheet.column_dimensions[column_letter].width = max_len

def create_interactive_heatmap(df):
    # Convert the DataFrame to binary: 1 if a rule is present, 0 if it's "Rule not in policy"
    binary_df = df.applymap(lambda x: 1 if x != "Rule not in policy" else 0)

    # Plot the interactive heatmap using Plotly
    fig = px.imshow(binary_df, labels=dict(x="Rules", y="Policies"), x=binary_df.columns, y=binary_df.index)
    fig.update_layout(title="Interactive Policy Comparison Heatmap", xaxis_nticks=36)
    fig.show()

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

    # Create the interactive heatmap using Plotly
    create_interactive_heatmap(df)

    print(f"Comparison saved to {args.output}")

if __name__ == "__main__":
    main()
