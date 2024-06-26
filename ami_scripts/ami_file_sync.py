#!/usr/bin/env python3

import argparse
import csv
import re
import subprocess

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process and sync files based on AMI IDs.')
    parser.add_argument('-s', '--spec', help='SPEC AMI Export, a CSV file of AMI IDs with migration status')
    parser.add_argument('-i', '--input', help='CSV file with a single column of AMI IDs')
    parser.add_argument('-p', '--pathlist', required=True, help='CSV file of file paths')
    parser.add_argument('-d', '--destination', required=True, help='Destination directory for rsynced files')
    parser.add_argument('-m', '--mode', choices=['check', 'rsync'], required=True, help='Operation mode: check or rsync')
    parser.add_argument('-f', '--filetypes', nargs='+', help='List of file extensions to include in rsync')
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    spec_list = []
    if args.spec:
        with open(args.spec, 'r', encoding='utf-8', errors='ignore') as fh:
            reader = csv.DictReader(fh)
            for record in reader:
                if record['migration_status'] == 'Migrated':
                    spec_list.append(record['ref_ami_id'])
    elif args.input:
        with open(args.input, 'r', encoding='utf-8', errors='ignore') as fh:
            reader = csv.DictReader(fh)
            for record in reader:
                spec_list.append(record['id'])

    patterns = {ami_id: re.compile(r'\b{}\b'.format(re.escape(ami_id))) for ami_id in spec_list}

    with open(args.pathlist, 'r', encoding='utf-8', errors='ignore') as fh:
        path_list = fh.read().splitlines()

    found_ami_ids = set()

    for path in path_list:
        for ami_id, pattern in patterns.items():
            if pattern.search(path):
                found_ami_ids.add(ami_id)
                if args.mode == 'rsync' and any(path.endswith(ext) for ext in args.filetypes):
                    rsync_call = ["rsync", "-rtv", "--progress", path, args.destination]
                    subprocess.call(rsync_call)
                break

    if args.mode == 'check':
        not_found_ami_ids = set(spec_list) - found_ami_ids
        print(f"AMI IDs found: {len(found_ami_ids)}")
        print(f"AMI IDs not found: {len(not_found_ami_ids)}")
        if not_found_ami_ids:
            print("The following AMI IDs were not found:")
            for ami_id in not_found_ami_ids:
                print(ami_id)

if __name__ == '__main__':
    main()
