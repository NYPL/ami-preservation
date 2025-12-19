#!/usr/bin/env python3

import argparse
import os
import subprocess
import bagit
import glob
import shutil
import json
from collections import Counter

def get_args():
    parser = argparse.ArgumentParser(description='Validate a directory of JSON files')
    parser.add_argument('-m', '--metadata',
                        help = 'path to the directory of JSON schema files', required=True)
    parser.add_argument('-d', '--directory',
                        help = 'path to the directory of JSON', required=True)
    args = parser.parse_args()
    return args

def get_directory(args):
    try:
        test_directory = os.listdir(args.directory)
    except OSError:
        exit('please retry with a valid directory')
    try:
        test_directory2 = os.listdir(args.metadata)
    except OSError:
        exit('please retry with a valid directory')
    source_directory = args.directory
    metadata_directory = args.metadata

    return source_directory, metadata_directory

def get_info(source_directory, metadata_directory):
    json_list = []
    for root, dirs, files in os.walk(source_directory):
        for file in files:
            if file.endswith('.json'):
                if file.startswith(('premis-events', '.')):
                    pass
                else:
                    item_path = os.path.join(root, file)
                    filename = os.path.basename(item_path)
                    json_list.append(item_path)

    print('\nCounts by Type:\n')
    types = []
    for file in json_list:
        with open(file, 'r', encoding='utf-8-sig') as jsonFile:
            data = json.load(jsonFile)
            types.append(data['source']['object']['type'])
    print(Counter(types))
    print('\n')
    print('JSON Validation:\n')

    schema_directory = os.path.join(metadata_directory, 'versions/2.0/schema')

    os.chdir(schema_directory)

    for file in json_list:
        with open(file, 'r', encoding='utf-8-sig') as jsonFile:
            data = json.load(jsonFile)
            if data['source']['object']['type'] == 'video cassette analog':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_videocassetteanalog.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['type'] == 'video cassette digital':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_videocassettedigital.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['type'] == 'video reel':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_videoreel.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['type'] == 'video optical disc':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_videoopticaldisc.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['type'] == 'audio cassette analog':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_audiocassetteanalog.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['type'] == 'audio reel analog':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_audioreelanalog.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['type'] == 'audio cassette digital':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_audiocassettedigital.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['type'] == 'audio reel digital':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_audioreeldigital.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['type'] == 'audio optical disc':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_audioopticaldisc.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['type'] == 'audio grooved disc':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_audiogrooveddisc.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['type'] == 'audio grooved cylinder':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_audiogroovedcylinder.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['type'] == 'audio magnetic wire':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_audiomagneticwire.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['format'] in ('8mm film, silent', '8mm film, optical sound', 
                                                        '8mm film, magnetic sound', 'Super 8 film, silent', 
                                                        'Super 8 film, optical sound', 'Super 8 film, magnetic sound', 
                                                        '16mm film, silent', '16mm film, optical sound', '16mm film, magnetic sound', 
                                                        '35mm film, silent', '35mm film, optical sound', '35mm film, magnetic sound', 
                                                        '9.5mm film, silent', 'Double 8mm film, silent'):
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_motionpicturefilm.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            
            elif data['source']['object']['format'] in ('16mm film, optical track', '16mm film, full-coat magnetic sound', 
                                                        '35mm film, optical track', '35mm film, full-coat magnetic sound'):
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_audiofilm.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            elif data['source']['object']['type'] == 'data optical disc':
                ajv_command = [
                    'ajv',
                    'validate',
                    '-s',
                    '../schema/digitized_dataopticaldisc.json',
                    '-r',
                    '../schema/fields.json',
                    '-d', file,
                    '--all-errors',
                    '--errors=json'
                    ]
            subprocess.call(ajv_command)

def main():
    arguments = get_args()
    source, metadata = get_directory(arguments)
    json_info = get_info(source, metadata)


if __name__ == '__main__':
    main()
    exit(0)
