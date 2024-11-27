#!/usr/bin/env python3 

import argparse
from pathlib import Path
import json
import re
import subprocess
from tqdm import tqdm
import textwrap

# Old MediaConch policies:
AUDIO_ANALOG = 'MediaConch_NYPL-FLAC_Analog.xml'
AUDIO_DIGITAL = 'MediaConch_NYPL-FLAC_Digital.xml'
# FILM_35_PM = 'MediaConch_NYPL_35mFilmPM.xml'
# FILM_8_16_PM = 'MediaConch_NYPL_8-16mmFilmPM.xml'
# FILM_MZ = 'MediaConch_NYPL_filmMZ.xml'
# FILM_SC = 'MediaConch_NYPL_filmSC.xml'
# VIDEO_PM = 'MediaConch_NYPL_FFV1MKV.xml'
# VIDEO_SC = 'MediaConch_NYPL_video_SC.xml'

# New MediaConch policies:
# AUDIO_ANALOG = ''
# AUDIO_DIGITAL = ''
# FILM_16_PM = '2024_film16_PM.xml'
# FILM_35_PM = '2024_film35_PM.xml'
# FILM_MZ = '2024_film_MZ.xml'
# FILM_SC = '2024_film_SC.xml'
VIDEO_PM = '2024_video_PM.xml'
VIDEO_SC = '2024_video_SC.xml'

# Newer MediaConch film policies:
FILM16_PM_COMP = '2024_film16_PM_compsound.xml'
FILM16_PM_SLNT = '2024_film16_PM_silent.xml'
FILM35_PM_COMP = '2024_film35_PM_compsound.xml'
FILM35_PM_SLNT = '2024_film35_PM_silent.xml'
FILM_MZ_COMP = '2024_film_MZ_compsound.xml'
FILM_MZ_SLNT = '2024_film_MZ_silent.xml'
FILM_SC_COMP = '2024_film_SC_compsound.xml'
FILM_SC_SLNT = '2024_film_SC_silent.xml'

# More new policies:
VIDEO_SC_OPTDV = '2024_video_SC_optdv.xml'

def parse_args():

    def dir_exists(dir):
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
    parser.add_argument('-fs', '--fail=short',
                        dest='format_fail',
                        help='Print only the first line of MediaConch text output for "fail!" results',
                        action='store_true')
    parser.add_argument('-ff', '--fail=full',
                        dest='format_fail',
                        help='Print the full MediaConch text output for each "fail!" result (default)',
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
    return parser.parse_args()

def get_asset_paths(dir_path):
    non_asset_exts = ('cue', 'framemd5', 'jpeg', 'jpg', 'json', 'old', 'scc', 'txt')
    asset_paths = [item for item in dir_path.rglob('*') 
                   if (item.is_file() and 
                       not (item.name.startswith('.') or 
                            item.suffix.lower().lstrip('.') in non_asset_exts))]
    return sorted(asset_paths)

def assign_policy(jformat, jrole, jtype):
    
    def assign_audio_policy():
        if re.search('digital|optical', jtype):
            policy = AUDIO_DIGITAL
        else:
            policy = AUDIO_ANALOG
        return policy

    # def assign_film_policy(): # with policies covering all mp film sound configurations
    #     if re.search('full-coat|track', jformat):
    #         policy = AUDIO_ANALOG
    #     elif jrole == 'sc':
    #         policy = FILM_SC
    #     elif jrole == 'mz':
    #         policy = FILM_MZ
    #     else:
    #         if not re.search('35', jformat):
    #             policy = FILM_16_PM
    #         else:
    #             policy = FILM_35_PM
    #     return policy

    def assign_film_policy(): # with different policies for silent and composite sound film

        def sort_mp_film(silent_policy, compsound_policy):
            if re.search('silent', jformat):
                policy = silent_policy
            else:
                policy = compsound_policy
            return policy

        if re.search('full-coat|track', jformat):
            policy = AUDIO_ANALOG
        elif jrole == 'sc':
            policy = sort_mp_film(FILM_SC_SLNT, FILM_SC_COMP)
        elif jrole == 'mz':
            policy = sort_mp_film(FILM_MZ_SLNT, FILM_MZ_COMP)
        else:
            if not re.search('35', jformat):
                policy = sort_mp_film(FILM16_PM_SLNT, FILM16_PM_COMP)
            else:
                policy = sort_mp_film(FILM35_PM_SLNT, FILM35_PM_COMP)
        return policy
    
    # def assign_video_policy(): #old version
    #     if jrole == 'sc':
    #         policy = VIDEO_SC
    #     else:
    #         if re.search('optical', jtype):
    #             policy = None
    #         else:
    #             policy = VIDEO_PM
    #     return policy
    
    def assign_video_policy(): #new version test: diff policy for SC from optical source (and dv? ...incomplete/untested)  

        def sort_video(v_sc_policy, v_pm_policy):
            if jrole == 'sc': 
                policy = v_sc_policy
            else: 
                policy = v_pm_policy
            return policy

        if re.search('optical', jtype):
            policy = sort_video(VIDEO_SC_OPTDV, None)
        elif re.search('dv', jtype):
            policy = sort_video(VIDEO_SC_OPTDV, VIDEO_PM) #to do!
        else:
            policy = sort_video(VIDEO_SC, VIDEO_PM)
        return policy

    if re.search('audio', jtype):
        policy = assign_audio_policy()
    elif re.search('film', jtype):
        policy = assign_film_policy()
    elif re.search('video', jtype):
        policy = assign_video_policy()
    else:
        policy = None
    return policy

def sort_assets(asset_paths):
    eligible, ineligible, json_invalid, json_missing = [], [], [], []
    for asset_path in asset_paths:
        json_path = asset_path.with_suffix('.json')
        try:
            with open(json_path, 'r', encoding='utf-8-sig') as jfile:
                data = json.load(jfile)
                jformat = data['source']['object']['format']
                jrole = data['asset']['fileRole']
                jtype = data['source']['object']['type']
        except FileNotFoundError:
            json_missing.append(asset_path)
            continue
        except KeyError:
            json_invalid.append(asset_path)
            continue
        policy = assign_policy(jformat.lower(), jrole.lower(), jtype.lower())
        description = f'{jtype} -- {jformat} -- {jrole} (policy = {policy})'
        idict = dict(asset_path=asset_path, policy=policy, description=description)
        if not policy:
            ineligible.append(idict)
        else:
            eligible.append(idict)
    return eligible, ineligible, json_invalid, json_missing

def build_dol(dol, key, ilist_item):
    if key not in dol.keys():
        dol[key] = []
    dol[key].append(ilist_item)

def bold(text):
    return f'\033[1m{text}\033[0m'

def print_dol(dol): 
    for key, ilist in sorted(dol.items()):
        print(bold(f'\n{key}:'))
        for item in ilist:
            print(item)

def report_sorted(orig_lod, val_to_print):
    new_dol = {}
    for idict in orig_lod:
        build_dol(new_dol, idict['description'], idict[val_to_print])
    print_dol(new_dol)

def print_json_problem_list(prob_list, error_msg):
    count = len(prob_list)
    if count > 0:
        print(f"\n\n{bold('ERROR:')} \n{count} assets' jsons are {error_msg}: assets CANNOT be sorted:")
        for item in prob_list:
            print(item)
    return count

def print_ineligible(ineligible):
    count = len(ineligible)
    if count > 0:
        print(f'\n\n{count} assets are MediaConch INELIGIBLE'
              f'\nThe following types/formats/roles are not subject to any MediaConch policy:')
        report_sorted(ineligible, 'asset_path')
    return count

def check_policy_paths(policy_paths):
    bad_p_paths = [item for item in set(policy_paths) if not item.exists()]
    if len(bad_p_paths) > 0:
        print(f'\n{bold("WARNING:")} \nThe following policy paths DO NOT exist (commands will result in error):')
        for item in bad_p_paths:
            print(item)
        print()

def prepare_mc_commands(eligible, policies_dir):
    print('Preparing MediaConch commands...')
    policy_paths = []
    for idict in eligible:
        policy_path = policies_dir.joinpath(idict['policy'])
        idict['command'] = ['mediaconch', '-p', policy_path, idict['asset_path']]
        policy_paths.append(policy_path)
    check_policy_paths(policy_paths)

def run_command(command):
    try:
        process = subprocess.run(command, check=True, timeout=300, text=True, capture_output=True)
        output = process.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        output = str(e)
    return output

def get_mc_output(eligible):
    print('Running MediaConch commands in subprocess...')
    for idict in tqdm(eligible):
        idict['output'] = run_command(idict['command'])

def format_result(result, formatting):
    if formatting == True:
        result = result.split('\n')[0]
    return result

def format_error(result, idict):
    indent = ' '*9
    result = '\n'.join(textwrap.wrap(result, initial_indent=indent, subsequent_indent=indent))
    return f"ERROR! {idict['asset_path']}\n   --  Subprocess returned: \n{result}"

def parse_output(eligible, format_pass, format_fail):
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
    print('Results:')
    if sort_results == True:
        report_sorted(eligible, 'result')
    else:
        print()
        for idict in eligible:
            print(idict['result'])

def summarize(asset_count, j_miss_count, json_inv_count, inelig_count, elig_count, p_count, f_count, e_count):
    prob_count = j_miss_count + json_inv_count
    print(f"\n{asset_count} assets found and sorted for MediaConch eligibility:"
          f'\n\t{elig_count} eligible'
          f'\n\t{inelig_count} ineligible')
    if prob_count != 0:
        print(f'\t{prob_count} problems were encountered during attempted sorting (see ERRORS '
              f'reported above) -- MediaConch eligibility COULD NOT BE DETERMINED for these assets')
    print(f'\n{elig_count} MediaConch checks were run for eligible assets:'
          f'\n\t{p_count} pass'
          f'\n\t{f_count} fail')
    if e_count != 0:
        print(f'\t{e_count} problems were encountered during attempted MediaConch check (see ERRORS'
              f' in results above) -- policy conformance COULD NOT BE DETERMINED for these assets')
    print()

def main():
    args = parse_args()
    print("\nSearching for assets... \nSearching for assets' json metadata files..." 
          "\nParsing jsons and sorting assets' eligibility for MediaConch evaluation...")
    asset_paths = get_asset_paths(args.project_dir)
    asset_count = len(asset_paths)
    eligible, ineligible, json_invalid, json_missing = sort_assets(asset_paths)
    print(f'\n{asset_count} assets found:')
    j_miss_count = print_json_problem_list(json_missing, 'MISSING')
    json_inv_count = print_json_problem_list(json_invalid, 'INVALID')
    inelig_count = print_ineligible(ineligible)
    elig_count = len(eligible)
    print(f'\n\n{elig_count} assets are MediaConch ELIGIBLE')
    prepare_mc_commands(eligible, args.policies_dir)
    get_mc_output(eligible)
    p_count, f_count, e_count = parse_output(eligible, args.format_pass, args.format_fail)
    report_results(eligible, args.sort_results)
    print(f'\n\nSummary for {args.project_dir}:')
    summarize(asset_count, j_miss_count, json_inv_count, inelig_count, elig_count, p_count, f_count, e_count)
if __name__ == '__main__':
    main()
