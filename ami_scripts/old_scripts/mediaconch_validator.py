#!/usr/bin/env python3 

import argparse
import json
import logging
import os
import re
import subprocess
from datetime import datetime

"""
    Classifies digital assets based on their corresponding json metadata files, 
    runs the appropriate MediaConch policy checks in subprocess, 
    and outputs MediaConch results to a CSV in the user's home directory.
"""

MEDIACONCH_POLICIES =  {
    'audio_analog': 'MediaConch_NYPL-FLAC_Analog.xml', 
    'audio_digital': 'MediaConch_NYPL-FLAC_Digital.xml', 
    'video_pm': 'MediaConch_NYPL_FFV1MKV.xml', 
    'video_sc': 'MediaConch_NYPL_video_SC.xml', 
    'film_35_pm': 'MediaConch_NYPL_35mFilmPM.xml', 
    'film_8_16_pm': 'MediaConch_NYPL_8-16mmFilmPM.xml', 
    'film_mz': 'MediaConch_NYPL_filmMZ.xml', 
    'film_sc': 'MediaConch_NYPL_filmSC.xml'
    }

LOGGER = logging.getLogger(__name__)


def configure_logging():
    log_format = '\n%(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format)


def make_parser():

    def valid_dir(dir: str) -> str:
        """Check if directory exists"""
        
        if dir.endswith('/'):
            dir = dir.rstrip('/')
        if not os.path.isdir(dir):
            exit(LOGGER.error(f'Not a valid directory: \n{dir}\n'))
        return dir

    def policy_dir(dir: str) -> str:
        """Check if directory contains MediaConch policies"""
       
        valid_dir(dir)
        missing_policies = [item for item in list(MEDIACONCH_POLICIES.values()) if item not in os.listdir(dir)]
        if missing_policies:
            exit(LOGGER.error(f'MediaConch policies missing from -p directory: \n{chr(10).join(missing_policies)}'))
        return dir

    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--directory',
                        dest = 'project_dir',
                        help = 'Path to directory of AMI bags',
                        required=True,
                        type = valid_dir)
    parser.add_argument('-p', '--policies',
                        dest = 'policies_dir',
                        help = 'Path to directory of MediaConch policies',
                        required=True,
                        type = policy_dir)
    return parser


def get_jsons_and_assets(dir: str) -> list:
    """Build lists of json metadata files and asset files from a directory"""

    print('\n*** Searching for jsons and media assets...')
    
    json_paths = []
    asset_paths = []
    for dirpath, dirnames, filenames in os.walk(dir):
        for filename in filenames:
            if (
                filename.startswith(('.', 'premis-events')) 
                or
                filename.endswith(('txt', 'framemd5', 'cue'))
                ):
                pass
            elif filename.endswith('json'):
                json_paths.append(os.path.join(dirpath, filename))
            else:
                asset_paths.append(os.path.join(dirpath, filename))
    return json_paths, asset_paths


def compare_lists(asset_paths: list, json_paths: list) -> list:
    """Compare lists of jsons and assets, return list of unmatched jsons"""

    print(f'\n*** {len(json_paths)} jsons and {len(asset_paths)} assets found: matching jsons to assets...')
    
    extra_jsons = []
    for item in json_paths:
        if item.split('.')[0] not in [item.split('.')[0] for item in asset_paths]:
            LOGGER.error(f'unmatched json (no corresponding asset): \n{item}')
            extra_jsons.append(item)

    for item in asset_paths:
        if item.split('.')[0] not in [item.split('.')[0] for item in json_paths]:
            LOGGER.error(f'unmatched asset (no corresponding json): \n{item}')
    
    return(extra_jsons)

def get_matched_jsons(dir: str) -> list:
    """Compare lists of jsons to unmatched jsons, return matched jsons only"""

    json_paths, asset_paths = get_jsons_and_assets(dir)
    extra_jsons = compare_lists(asset_paths, json_paths)
    matched_json_paths = [item for item in json_paths if item not in extra_jsons]
    
    print(f'\n*** {len(matched_json_paths)} matched json-asset pairs found: analyzing jsons...')

    return matched_json_paths
        

def get_json_values(json_path: str) -> tuple | None:
    """Open a json file, return a tuple of 4 values"""
    
    fh = open(json_path, 'r', encoding='utf-8-sig')
    data = json.load(fh)
    
    try:
        json_values = (
            data['source']['object']['type'],
            data['source']['object']['format'],
            data['asset']['fileRole'].lower(),
            data['technical']['extension'].lower()
        )
    except KeyError:
        LOGGER.error(f'json missing one or more required fields: \n{json_path}')
        json_values = None
    
    fh.close()
    return json_values
    

def get_asset_path(json_path: str) -> str | None:
    """Build an asset path from a json path"""

    file_ext = get_json_values(json_path)[3]
    asset_path = json_path.split('.')[0] + '.' + file_ext
    if not os.path.exists(asset_path):
        LOGGER.error(f'json technical.extension value is incorrect: \n{json_path}')
        asset_path = None
    return asset_path


def classify_asset(json_path: str) -> str | None:
    """Classify assets based on json values, return the asset class name"""

    source_type, source_format, file_role, file_ext = get_json_values(json_path)

    def classify_audio() -> str | None:
        if (re.search('digital|optical', source_type) 
            and source_format != 'U-matic/PCM'):
            audio_class = 'audio_digital'
        else:
            audio_class = 'audio_analog'
        return audio_class
    
    def classify_video() -> str | None:
        if file_role == 'sc':
            video_class = 'video_sc'
        elif file_ext == 'iso':
            video_class = 'iso_pm'
        else:
            video_class = 'video_pm'
        return video_class
    
    def classify_film() -> str | None:
        if re.search('track|full-coat', source_format):
            film_class = 'audio_analog'
        elif file_role == 'sc':
            film_class = 'film_sc'
        elif file_role == 'mz':
            film_class = 'film_mz'
        elif not source_format.startswith('35'):
            film_class = 'film_8_16_pm'
        else:
            film_class = 'film_35_pm'
        return film_class
    
    if re.search('audio', source_type):
        asset_class = classify_audio()
    elif re.search('video', source_type):
        asset_class = classify_video()
    elif re.search('film', source_type):
        asset_class = classify_film()
    elif source_type == 'data optical disc':
        asset_class = 'data_disc'
    else:
        asset_class = 'unknown'
        LOGGER.error(f'json source.object.type value not recognized: \n{json_path}')
    return asset_class


def get_log_path(project_dir: str) -> str:
    """Build a path to create a CSV output log in the user's home directory"""

    log_path = f"{os.environ['HOME']}/mediaconch_{os.path.basename(project_dir)}_{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
    return log_path


def get_mediaconch_command(policies_dir: str, asset_class: str, asset_path: str) -> list:
    """Look up MediaConch policy from asset class, build MediaConch command as a list"""

    policy_name = MEDIACONCH_POLICIES[asset_class]
    mediaconch_command = ['mediaconch', '-p', f'{policies_dir}/{policy_name}', asset_path]
    return mediaconch_command


def main():
    
    configure_logging()

    parser = make_parser()
    args = parser.parse_args()

    log_path = get_log_path(args.project_dir)
    wfh = open(log_path, 'w')
    
    json_errors = 0
    data_discs = []
    iso_pms = []
    command_count = 0

    for json_path in get_matched_jsons(args.project_dir):

        if not get_json_values(json_path):
            json_errors += 1
            continue
        
        asset_path = get_asset_path(json_path)
        if not asset_path:
            json_errors += 1
            continue
        
        asset_class = classify_asset(json_path)
        if asset_class == 'data_disc':
            data_discs.append(asset_path)
        elif asset_class == 'iso_pm':
            iso_pms.append(asset_path)
        elif asset_class not in list(MEDIACONCH_POLICIES.keys()):
            json_errors += 1
        else:
            mediaconch_command = get_mediaconch_command(args.policies_dir, asset_class, asset_path)
            command_count += 1
            subprocess.run(mediaconch_command, stdout=wfh)
        
    wfh.close()

    print(f'\n*** {json_errors + len(data_discs) + len(iso_pms) + command_count} jsons analyzed:')
    if json_errors > 0:
        print(f'\n{json_errors} jsons have errors (see messages above): assets CANNOT BE EVALUATED !')
    if data_discs:
        print(f'\n{len(data_discs)} data discs will not be evaluated because there is no MediaConch policy: \n{chr(10).join(data_discs)}')
    if iso_pms:
        print(f'\n{len(iso_pms)} ISO PMs will not be evaluated because there is no MediaConch policy: \n{chr(10).join(iso_pms)}')
    
    print(f'\n{command_count} assets were evaluated against MediaConch policies. See results here: \n{log_path}\n')


if __name__ == '__main__':
    main()
