#!/usr/bin/env python3

import argparse
import csv
import re
import subprocess

# Setting up argparse for command-line arguments
parser = argparse.ArgumentParser(description='Process and sync files based on AMI IDs.')
parser.add_argument('-s', '--spec', required=True, help='SPEC AMI Export, a CSV file of AMI IDs')
parser.add_argument('-p', '--pathlist', required=True, help='CSV file of file paths')
parser.add_argument('-d', '--destination', required=True, help='Destination directory for rsynced files')
parser.add_argument('-m', '--mode', choices=['check', 'rsync'], required=True, help='Operation mode: check or rsync')
args = parser.parse_args()

# Reading AMI IDs from the SPEC AMI Export CSV
spec_list = []
with open(args.spec, 'r', encoding='utf-8', errors='ignore') as fh:
    reader = csv.DictReader(fh)
    for record in reader:
        if record['migration_status'] == 'Migrated':
            spec_list.append(record['ref_ami_id'])

# Pre-compiling regular expressions for AMI IDs
patterns = {ami_id: re.compile(r'\b{}\b'.format(re.escape(ami_id))) for ami_id in spec_list}

# Reading the list of paths from the provided file
with open(args.pathlist, 'r', encoding='utf-8', errors='ignore') as fh:
    path_list = fh.read().splitlines()

# Set for tracking found AMI IDs
found_ami_ids = set()

# Searching for AMI IDs in the file paths
for path in path_list:
    for ami_id, pattern in patterns.items():
        if pattern.search(path):
            found_ami_ids.add(ami_id)
            if args.mode == 'rsync' and path.endswith(('em.flac', 'pm.iso')):
                rsync_call = ["rsync", "-rtv", "--progress", path, args.destination]
                subprocess.call(rsync_call)
            break  # Stop searching if AMI ID is found in this path

if args.mode == 'check':
    # If in check mode, report AMI IDs found and not found
    not_found_ami_ids = set(spec_list) - found_ami_ids
    print(f"AMI IDs found: {len(found_ami_ids)}")
    print(f"AMI IDs not found: {len(not_found_ami_ids)}")
    if not_found_ami_ids:
        print("The following AMI IDs were not found:")
        for ami_id in not_found_ami_ids:
            print(ami_id)
