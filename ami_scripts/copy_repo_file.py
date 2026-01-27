#!/usr/bin/env python3

import argparse
import csv
import pathlib
import re
import subprocess
import sys


FORMAT_TO_EXT = {
    'DV': '.dv',
    'FLAC': '.flac',
    'Matroska': '.mkv',
    'Quicktime': '.mov',
    'MPEG-4': '.mp4',
    'Wave': '.wav'
}


TYPE_TO_AV = {
    'hd': '.mp4',
    'sd': '.mp4',
    '': '.m4a'
}


CAPTURE_BUCKET = 'repo-transcoded-web-media'


def _make_parser():

    def validate_object(id):
        # Allow underscores in ID for cases like 1126_7993
        if not re.match(r'^[a-z0-9_]+$', id):
            raise argparse.ArgumentTypeError(
                f'Object ID must have no spaces e.g. ncow 421: {id}'
            )

        return id

    def validate_file(p):
        path = pathlib.Path(p)

        if not path.is_file():
            raise argparse.ArgumentTypeError(
                f'File path does not exist: {path}'
            )

        return p

    def validate_dir(p):
        path = pathlib.Path(p)

        if not path.is_dir():
            raise argparse.ArgumentTypeError(
                f'Directory path does not exist: {path}'
            )

        return p

    parser = argparse.ArgumentParser()
    parser.description = 'rsync a file from repo'
    parser.add_argument(
        '-i', '--object',
        action='append',
        type=validate_object,
        help='cms id of the object to retrieve files for',
        required=False)
    parser.add_argument(
        '-a', '--assets',
        help='csv of assets in repo',
        type=validate_file,
        default='~/assets.csv')
    parser.add_argument(
        '--uuid',
        action='append',
        help='uuid of file in repo')
    parser.add_argument(
        '-r', '--repo',
        help='path to repo folder, probably /Volumes/repo/',
        type=validate_dir)
    parser.add_argument(
        '-s', '--servicecopies',
        help='switch to download service files from S3',
        action='store_true',
        default=False)
    parser.add_argument(
        '-d', '--destination',
        help='path to destination',
        type=validate_dir,
        default='/Volumes/video_repository/Working_Storage/')

    return parser


def extract_id(filename):
    clean_name = pathlib.Path(filename).stem
    components = clean_name.split('_')
    
    if len(components) < 2:
        return None
    
    # UPDATED HEURISTIC:
    # If the 2nd and 3rd parts are numbers (e.g. 1126 and 7993), join them.
    # This handles 'mao', 'mss', or any other prefix where the ID is split numeric.
    if len(components) >= 3 and components[1].isdigit() and components[2].isdigit():
        return f'{components[1]}_{components[2]}'

    # Fallback for standard IDs like scvisualvrb2049 (which is not just digits)
    return components[1]


def get_accessfmt(typecode):
    if typecode in TYPE_TO_AV.keys():
        type = TYPE_TO_AV[typecode]
    else:
        type = '.unknown'

    return type


def parse_assets(path):
    with open(path, mode='r') as file:
        reader = csv.DictReader(file)

        if not all(x in reader.fieldnames for x in ['name', 'uuid']):
            raise ValueError(
                'Assets file is missing one or more required header values: '
                'name and uuid'
            )

        assets_dict = {}
        uuid_dict = {}

        for row in reader:
            object_id = extract_id(row['name'])
            
            # Populate ID Dictionary
            if object_id:
                if object_id not in assets_dict.keys():
                    assets_dict[object_id] = []
                assets_dict[object_id].append(row)
            
            # Populate UUID Dictionary
            if row['uuid']:
                uuid_dict[row['uuid']] = row

    return assets_dict, uuid_dict


def get_object_entries(object_id, assets_dict):
    entries = []
    if object_id in assets_dict.keys():
        for file in assets_dict[object_id]:
            entries.append(
                {
                    'object_id': object_id,
                    'filename': file['name'],
                    'uuid': file['uuid'],
                    'capture_uuid': file['capture_uuid'],
                    'access_fmt': get_accessfmt(file['type'])
                }
            )

    if not entries:
        return None

    return entries


def get_uuid_path(uuid):
    if len(uuid.split('-')) != 5:
        raise ValueError(f'UUID is not formatted correctly: {uuid}')

    file_path = pathlib.Path(
        uuid[0:2]).joinpath(uuid[0:4]) \
        .joinpath(uuid[4:8]).joinpath(uuid[9:13]) \
        .joinpath(uuid[14:18]).joinpath(uuid[19:23]) \
        .joinpath(uuid[24:28]).joinpath(uuid[28:32]) \
        .joinpath(uuid[32:34]).joinpath(uuid)
    return file_path


def get_extension(path):
    format = subprocess.run(
        ['mediainfo', '--Inform=General;%Format%,%FormatProfile%', path],
        capture_output=True
    ).stdout.decode('utf-8').strip().split(',')

    if len(format) > 1 and format[1] == 'Quicktime':
        format[0] = 'Quicktime'

    if format[0] in FORMAT_TO_EXT.keys():
        ext = FORMAT_TO_EXT[format[0]]
    else:
        ext = '.unknown'

    return ext


def run_rsync(source, dest):
    subprocess.call([
        'rsync', '-tv', '--progress',
        source, dest
    ])


def run_s3cp(source, dest):
    subprocess.call([
        'aws', 's3', 'cp',
        f's3://{CAPTURE_BUCKET}/{source}', dest
    ])


def main():
    parser = _make_parser()
    args = parser.parse_args()

    if not args.object and not args.uuid:
        print("Error: You must provide either an Object ID (-i) or a UUID (--uuid).")
        parser.print_help()
        sys.exit(1)

    assets_dict, uuid_dict = parse_assets(args.assets)

    in_repo = []
    
    # Handle IDs (-i)
    if args.object:
        for object_id in args.object:
            entries = get_object_entries(object_id, assets_dict)
            if entries:
                in_repo.extend(entries)
            else:
                print(f'Could not find files listed in CSV for ID: {object_id}')

    # Handle UUIDs (--uuid)
    if args.uuid:
        for uuid in args.uuid:
            if uuid in uuid_dict:
                file = uuid_dict[uuid]
                in_repo.append({
                    'object_id': extract_id(file['name']),
                    'filename': file['name'],
                    'uuid': file['uuid'],
                    'capture_uuid': file.get('capture_uuid'),
                    'access_fmt': get_accessfmt(file['type'])
                })
            else:
                print(f'Could not find file listed in CSV for UUID: {uuid}')

    for file in in_repo:
        dest = pathlib.Path(args.destination).joinpath(file['filename'])

        if args.servicecopies:
            capture_name = (
                f'{file["capture_uuid"]}/'
                f'{file["capture_uuid"]}-high{file["access_fmt"]}'
            )
            dest = dest.with_suffix(file["access_fmt"])
            print(f'Downloading {capture_name} to {dest}')
            run_s3cp(capture_name, dest)
        else:
            repo_path = pathlib.Path(args.repo).joinpath(
                get_uuid_path(file['uuid'])
            )
            
            if not repo_path.exists():
                print(f"Warning: Source file not found at {repo_path}")
                continue

            dest = dest.with_suffix(get_extension(repo_path))
            print(f'Downloading {repo_path} to {dest}')
            run_rsync(repo_path, dest)


if __name__ == '__main__':
    main()