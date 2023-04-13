#!/usr/bin/env python3

import argparse
import os
import json
import pandas as pd
import re

def get_args():
    parser = argparse.ArgumentParser(description='Prep CMS Excel for Import into AMIDB')
    parser.add_argument('-s', '--source',
                        help='path to the source XLSX', required=True)
    parser.add_argument('-w', '--workorder',
                        help='Work Order ID to apply to new XLSX', required=False)
    parser.add_argument('-d', '--destination',
                        help='path to the output directory', required=False)
    parser.add_argument('-c', '--config',
                        help='path to the config file', default='config.json', required=False)
    args = parser.parse_args()
    return args

def read_config(config_path):
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

def replace_characters(df, replacements):
    for column in df:
        for replacement in replacements:
            old_char = replacement['find']
            new_char = replacement['replace']
            df[column] = df[column].apply(lambda x: re.sub(old_char, new_char, x) if isinstance(x, str) else x)


def apply_format_fixes(df, format_fixes):
    for target_type, formats in format_fixes.items():
        for fmt in formats:
            df.loc[df['source.object.format'] == fmt, 'source.object.type'] = target_type


def apply_film_fix(df):
    film_formats = [
        "8mm film, silent",
        "8mm film, optical sound",
        "8mm film, magnetic sound",
        "Super 8 film, silent",
        "Super 8 film, optical sound",
        "Super 8 film, magnetic sound",
        "16mm film, silent",
        "16mm film, optical sound",
        "16mm film, magnetic sound",
        "35mm film, silent",
        "35mm film, optical sound",
        "35mm film, magnetic sound",
        "9.5mm film, silent",
        "Double 8mm film, silent"
    ]

    df.loc[(df['source.object.type'] == 'film') & df['source.object.format'].isin(film_formats), 'source.subObject.faceNumber'] = ''


def cleanup_excel(args):
    if args.source:
        excel_name = os.path.basename(args.source)
        clean_name = os.path.splitext(excel_name)[0] + '_CLEAN.xlsx'

        df = pd.read_excel(args.source)

        config = read_config(args.config)
        replace_characters(df, config['replacements'])
        apply_format_fixes(df, config['format_fixes'])
        apply_film_fix(df)

        # Additional cleanup code:
        df = df.drop('Filename (reference)', axis=1)
        if 'MMS Collection ID' in df.columns:
            df = df.drop('MMS Collection ID', axis=1)

        df['asset.fileRole'] = 'pm'

        # Schema fix
        df.loc[df['asset.schemaVersion'] == 2, 'asset.schemaVersion'] = '2.0.0'

        # Video face fix:
        df.loc[df['source.object.type'] == 'video cassette', 'source.subObject.faceNumber'] = ''
        df.loc[df['source.object.type'] == 'video reel', 'source.subObject.faceNumber'] = ''
        df.loc[df['source.object.type'] == 'video optical', 'source.subObject.faceNumber'] = ''

        # Audio optical fix
        df.loc[df['source.object.type'] == 'audio optical', 'source.object.type'] = 'audio optical disc'

        # Video optical fix
        df.loc[df['source.object.type'] == 'video optical', 'source.object.type'] = 'video optical disc'

        if args.workorder:
            df['WorkOrderId'] = args.workorder

        if args.destination:
            if os.path.exists(args.destination):
                output_path = os.path.join(args.destination, clean_name)
                df.to_excel(output_path, sheet_name='Sheet1', index=False)

def main():
    arguments = get_args()
    cleanup_excel(arguments)

if __name__ == '__main__':
    main()
    exit(0)


