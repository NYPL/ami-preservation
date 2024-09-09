#!/usr/bin/env python3 

import argparse
import json
from pathlib import Path
import re
import subprocess
from tqdm import tqdm

"""
    Finds all asset files in a directory, finds corresponding json metadata files, 
    classifies assets based on json values, chooses MediaConch policies for eligible assets, 
    runs policy checks in subprocess, and prints results to terminal.
"""

AUDIO_ANALOG = 'MediaConch_NYPL-FLAC_Analog.xml'
AUDIO_DIGITAL = 'MediaConch_NYPL-FLAC_Digital.xml'
FILM_35_PM = 'MediaConch_NYPL_35mFilmPM.xml'
FILM_8_16_PM = 'MediaConch_NYPL_8-16mmFilmPM.xml'
FILM_MZ = 'MediaConch_NYPL_filmMZ.xml'
FILM_SC = 'MediaConch_NYPL_filmSC.xml'
VIDEO_PM = 'MediaConch_NYPL_FFV1MKV.xml'
VIDEO_SC = 'MediaConch_NYPL_video_SC.xml'

def parse_args():

    def dir_exists(dir):
        """Exit if path to given directory does not exist"""
        dir_path = Path(dir)
        if not dir_path.exists():
            exit(f'\nERROR: directory does not exist: \n{dir}\n')
        return dir_path
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--directory',
                        dest='project_dir',
                        help='Path to directory of AMI bags (required)',
                        required=True,
                        type=dir_exists)
    parser.add_argument('-p', '--policies',
                        dest='policies_dir',
                        help='Path to directory of MediaConch policies (required)',
                        required=True,
                        type=dir_exists)
    parser.add_argument('-ff', '--fail=full',
                        dest='format_fail',
                        help='Print the full MediaConch text output for each "fail!" result (default)',
                        action='store_true')
    parser.add_argument('-fs', '--fail=short',
                        dest='format_fail',
                        help='Print only the first line of MediaConch text output for "fail!" results',
                        action='store_false')
    parser.add_argument('-pf', '--pass=full',
                        dest='format_pass',
                        help='Print the full MediaConch text output for each "pass!" result',
                        action='store_false')
    parser.add_argument('-ps', '--pass=short',
                        dest='format_pass',
                        help='Print only the first line of MediaConch text output for "pass!" results (default)',
                        action='store_true')
    parser.add_argument('-rf', '--results=flat',
                        dest='sort_results',
                        help='Print results in a single flat list',
                        action='store_false')
    parser.add_argument('-rs', '--results=sort',
                        dest='sort_results',
                        help='Print results grouped by type/format/role (default)',
                        action='store_true')
    parser.add_argument('-ua', '--umaticpcm=analog',
                        dest='umaticpcm_exception',
                        help='Use analog audio policy for U-matic/PCM',
                        action='store_false')
    parser.add_argument('-ud', '--umaticpcm=digital',
                        dest='umaticpcm_exception',
                        help='Use digital audio policy for U-matic/PCM (default)',
                        action='store_true')
    return parser.parse_args()

def get_asset_paths(dir_path):
    """From a given directory, build a list of assets by process of elimination"""
    asset_paths = []
    non_asset_extensions = ('cue', 'framemd5', 'jpeg', 'jpg', 'json', 'old', 'scc', 'txt')
    for item in dir_path.rglob('*'):
        if item.is_file():
            if not (item.name.startswith('.') or 
                    item.suffix.lower().lstrip('.') in non_asset_extensions):
                asset_paths.append(item)
    asset_count = len(asset_paths)
    print(f'\n\n{asset_count} assets found')
    return sorted(asset_paths), asset_count

def get_json_path(asset_path):
    """Infer a json path based on an asset path"""
    json_path = asset_path.with_suffix('.json')
    return json_path

def get_json_values(json_path):
    """Open a json file and get values from four specified fields"""
    fh = open(json_path, 'r', encoding='utf-8-sig')
    data = json.load(fh)
    json_values = (data['source']['object']['type'], 
                   data['source']['object']['format'], 
                   data['asset']['fileRole'], 
                   data['technical']['extension'])
    fh.close()
    return json_values

def try_json_values(asset_path):
    """Try to get json values from an inferred json path; return none if json does not exist or is invalid"""
    json_path = get_json_path(asset_path)
    try:
        json_values = get_json_values(json_path)
    except FileNotFoundError:
        print(f'\nERROR: json not found (asset CANNOT be sorted): \n{asset_path}')
        json_values = None
    except KeyError:
        print(f'\nERROR: invalid json (asset CANNOT be sorted): \n{asset_path}')
        json_values = None
    return json_values

def assign_policy(json_values, umaticpcm_exception):
    """Choose a MediaConch policy based on json values"""
    
    def assign_audio_policy():
        if re.search('digital|optical', j_type):
            policy = AUDIO_DIGITAL
            if j_format == 'u-matic/pcm':
                if umaticpcm_exception == True:
                    policy = AUDIO_ANALOG
        else:
            policy = AUDIO_ANALOG
        return policy
    
    def assign_film_policy():
        if re.search('full-coat|track', j_format):
            policy = AUDIO_ANALOG
        elif j_role == 'sc':
            policy = FILM_SC
        elif j_role == 'mz':
            policy = FILM_MZ
        else:
            if not re.search('35', j_format):
                policy = FILM_8_16_PM
            else:
                policy = FILM_35_PM
        return policy
    
    def assign_video_policy():
        if j_role == 'sc':
            policy = VIDEO_SC
        else:
            if j_ext == 'iso':
                policy = None
            else:
                policy = VIDEO_PM
        return policy
    
    j_type, j_format, j_role, j_ext = [item.lower() for item in json_values]
    if re.search('audio', j_type):
        policy = assign_audio_policy()
    elif re.search('film', j_type):
        policy = assign_film_policy()
    elif re.search('video', j_type):
        policy = assign_video_policy()
    else:
        policy = None
    return policy

def describe_asset(json_values, policy):
    """Assemble a short description based on json values and policy"""
    j_type, j_format, j_role, j_ext = [item.upper() for item in json_values]
    description = f'{j_type} -- {j_format} -- {j_role} (policy={policy})'
    return description

def sort_assets(assets, umaticpcm_exception):
    """From a list of assets, filter out assets with json issues, then build a dict for each remaining
    asset, finally sorting each dict into one of two lists of dicts depending on MediaConch eligibility"""
    print('Analyzing jsons and sorting assets...')
    ineligible = []
    eligible = []
    for asset_path in assets:
        json_values = try_json_values(asset_path)
        if not json_values:
            continue
        policy = assign_policy(json_values, umaticpcm_exception)
        description = describe_asset(json_values, policy)
        idict = {'asset_path': asset_path,  
                 'policy': policy,
                 'description': description}
        if not policy:
            ineligible.append(idict)
        else:
            eligible.append(idict)
    return ineligible, eligible

def build_dol(dol, key, item):
    """Append an item to an inner list in a dict of lists"""
    if key not in dol.keys():
        dol[key] = []
    dol[key].append(item)

def print_dol(dol): 
    """Loop through a dict of lists and print each key and each inner list item"""
    for key, ilist in sorted(dol.items()):
        print(f'\n\033[1m{key}\033[0m:')
        for item in ilist:
            print(item)

def report_sorted(orig_lod, val_to_print):
    """Convert a list of dicts to a dict of lists in order to print selected values in order sorted by description""" 
    new_dol = {}
    for idict in orig_lod:
        new_key = idict['description']
        new_ilist_item = idict[val_to_print]
        build_dol(new_dol, new_key, new_ilist_item)
    print_dol(new_dol)

def print_prelim_info(ineligible, eligible):
    """Print some preliminary information about asset sorting before running MediaConch checks"""
    inelig_count, elig_count = len(ineligible), len(eligible)
    if inelig_count > 0:
        print(f'\n\n{inelig_count} assets are MediaConch INELIGIBLE'
              f'\nThe following types/formats/roles are not subject to any MediaConch policy:')
        report_sorted(ineligible, 'asset_path')
    print(f'\n\n{elig_count} assets are MediaConch ELIGIBLE')
    return inelig_count, elig_count

def build_command(idict, policies_dir):
    """Build a MediaConch command in list form for use in subprocess"""
    asset_path = idict['asset_path']
    policy_path = policies_dir.joinpath(idict['policy'])
    command = ['mediaconch', '-p', policy_path, asset_path]
    return command

def prepare_mc_commands(eligible, policies_dir):
    """For each inner dict in a list of dicts, add key/value for MediaConch command"""
    for idict in eligible:
        command = build_command(idict, policies_dir)
        idict['command'] = command

def run_command(command):
    """Run a command in subprocess"""
    try:
        process = subprocess.run(command, check=True, timeout=300, text=True, capture_output=True)
        output = process.stdout
    except subprocess.CalledProcessError as e:
        output = str(e)
    except subprocess.TimeoutExpired as e:
        output = str(e)
    return output

def get_mc_output(eligible):
    """For each inner dict in a list of dicts, add key/value for MediaConch output"""
    print('Running MediaConch commands in subprocess...')
    for idict in tqdm(eligible):
        command = idict['command']
        output = run_command(command)
        idict['output'] = output

def format_result(result, formatting):
    """Format a 'pass!' or 'fail!' MediaConch result for printing"""
    if formatting == True:
        result = result.split('\n')[0]
    return result

def format_error(result, idict):
    """Format the return from a subprocess error as a result for printing"""
    error_result = f"ERROR! {idict['asset_path']}\n   --  Subprocess returned:\n\t{result}"
    return error_result

def parse_output(eligible, format_pass, format_fail):
    """For each inner dict in a list of dicts, tally & format output, then add key/value for formatted output"""
    p_count, f_count, e_count = 0, 0, 0
    for idict in eligible:
        result = idict['output'].rstrip('\n')
        if 'pass!' in result:
            p_count += 1
            result = format_result(result, format_pass)
        elif 'fail!' in result:
            f_count += 1
            result = format_result(result, format_fail)
        else:
            e_count +=1
            result = format_error(result, idict)
        idict['result'] = result
    return p_count, f_count, e_count

def report_results(eligible, sort_results):
    """Print MediaConch results"""
    print('Results:')
    if sort_results == True:
        report_sorted(eligible, 'result')
    else:
        print()
        for idict in eligible:
            print(idict['result'])
    
def summarize(asset_count, inelig_count, elig_count, p_count, f_count, e_count):
    """Print summaries of eligibility sorting and MediaConch output, plus any errors in sorting or output"""
    print('\n\nSummary:')
    prob_count = asset_count - inelig_count - elig_count
    print(f'\n{asset_count} assets found and sorted for MediaConch eligibility:'
          f'\n\t{elig_count} eligible'
          f'\n\t{inelig_count} ineligible')
    if prob_count != 0:
        print(f'\t{prob_count} problems were encountered during attempted sorting (see ERRORS '
              f'reported above) -- MediaConch eligibility COULD NOT BE DETERMINED for these assets')
    print(f'\n{elig_count} MediaConch checks were run for eligible assets:'
          f'\n\t{p_count} passed'
          f'\n\t{f_count} failed')
    if e_count != 0:
        print(f'\t{e_count} problems were encountered during attempted MediaConch check (see ERRORS'
              f' in results above) -- policy conformance COULD NOT BE DETERMINED for these assets')
    print()

def main():
    args = parse_args()
    assets, asset_count = get_asset_paths(args.project_dir)
    ineligible, eligible = sort_assets(assets, args.umaticpcm_exception)
    inelig_count, elig_count = print_prelim_info(ineligible, eligible)
    prepare_mc_commands(eligible, args.policies_dir)
    get_mc_output(eligible)
    pass_count, fail_count, error_count = parse_output(eligible, args.format_pass, args.format_fail)
    report_results(eligible, args.sort_results)
    summarize(asset_count, inelig_count, elig_count, pass_count, fail_count, error_count)

if __name__ == '__main__':
    main()
