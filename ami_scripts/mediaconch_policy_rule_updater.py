#!/usr/bin/env python3

import os
import argparse
import xml.etree.ElementTree as ET

def update_rule(file_path, old_name, new_name, new_operator, new_value):
    # Parse the XML file
    tree = ET.parse(file_path)
    root = tree.getroot()

    updated = False

    # Loop through all rules and find the one to modify
    for rule in root.findall(".//rule[@name='" + old_name + "']"):
        # Update the rule name if provided
        if new_name:
            rule.set('name', new_name)
        
        # Update the operator if provided
        if new_operator:
            rule.set('operator', new_operator)
        
        # Update the value if provided
        if new_value:
            rule.text = new_value
        
        updated = True
    
    if updated:
        # Save the modified XML back to the file
        tree.write(file_path)

    return updated

def process_directory(directory, old_name, new_name, new_operator, new_value):
    updated_policies = []
    non_updated_policies = []

    # Loop through all XML files in the directory
    for filename in os.listdir(directory):
        if filename.endswith(".xml"):
            file_path = os.path.join(directory, filename)
            print(f"Processing {file_path}...")

            updated = update_rule(file_path, old_name, new_name, new_operator, new_value)

            if updated:
                print(f"Updated rule in {file_path}")
                updated_policies.append(file_path)
            else:
                print(f"Rule not found, skipping {file_path}")
                non_updated_policies.append(file_path)

    return updated_policies, non_updated_policies

def main():
    parser = argparse.ArgumentParser(
        description="Update rules in MediaConch policies.\n\n"
                    "NOTE: You may need to use quotes in bash for arguments that contain spaces or special characters.\n"
                    "For example:\n"
                    "./mediaconch_policy_rule_updater.py -d /path/to/xml/files \\\n"
                    "-r \"Video/extra[1]/MaxSlicesCount is 24 or greater\" \\\n"
                    "-n \"Video/extra[1]/MaxSlicesCount is 48 or greater\" \\\n"
                    "-o \"=\" -v \"48\""
    )
    parser.add_argument(
        "-d", "--directory", required=True, help="Directory containing XML files"
    )
    parser.add_argument(
        "-r", "--rule", required=True, 
        help="Rule name to update (use quotes if it contains spaces or special characters)"
    )
    parser.add_argument(
        "-n", "--name", 
        help="New rule name (optional, use quotes if it contains spaces or special characters)"
    )
    parser.add_argument(
        "-o", "--operator", 
        help="New operator (optional, use quotes if it contains special characters)"
    )
    parser.add_argument(
        "-v", "--value", 
        help="New value (optional, use quotes if it contains special characters)"
    )
    args = parser.parse_args()

    updated_policies, non_updated_policies = process_directory(args.directory, args.rule, args.name, args.operator, args.value)

    # Report summary at the end
    print("\n=== Summary ===")
    print(f"Updated {len(updated_policies)} policies:")
    for policy in updated_policies:
        print(f"  - {policy}")

    print(f"Did not update {len(non_updated_policies)} policies (rule not found):")
    for policy in non_updated_policies:
        print(f"  - {policy}")

if __name__ == "__main__":
    main()
