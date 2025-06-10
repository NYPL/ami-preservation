#!/usr/bin/env python3 

import logging
import argparse
from pathlib import Path
import pandas as pd
import json
import re
import subprocess
from tqdm import tqdm
import xml.etree.ElementTree as ET
from collections import Counter

# New MediaConch policies:
# AUDIO_ANALOG = 'MediaConch_NYPL-FLAC_Analog.xml' # to do (old)
# AUDIO_DIGITAL = 'MediaConch_NYPL-FLAC_Digital.xml' # to do (old)
# AUDIO_OPTICAL = 'MediaConch_NYPL-FLAC_Digital.xml' # to do (old)
AUDIO_ANALOG_CYLINDER = '2024_audio_analog_cylinder.xml'
AUDIO_ANALOG = '2024_audio_analog.xml'
AUDIO_DIGITAL_DAT = '2024_audio_digital_DAT.xml'
AUDIO_DIGITAL = '2024_audio_digital.xml'
AUDIO_OPTICAL = '2024_audio_optical.xml'
FILM16_PM_COMP = '2024_film16_PM_compsound.xml'
FILM16_PM_FLEX = '2024_film16_PM.xml'
FILM16_PM_SLNT = '2024_film16_PM_silent.xml'
FILM35_PM_COMP = '2024_film35_PM_compsound.xml'
FILM35_PM_FLEX = '2024_film35_PM.xml'
FILM35_PM_SLNT = '2024_film35_PM_silent.xml'
FILM_MZ_COMP = '2024_film_MZ_compsound.xml'
FILM_MZ_FLEX = '2024_film_MZ.xml'
FILM_MZ_SLNT = '2024_film_MZ_silent.xml'
FILM_SC_COMP = '2024_film_SC_compsound.xml'
FILM_SC_FLEX = '2024_film_SC.xml'
FILM_SC_SLNT = '2024_film_SC_silent.xml'
VIDEO_PM = '2024_video_PM.xml'
VIDEO_PM_DV = '2024_video_PM_DV.xml'
VIDEO_PM_HDV = VIDEO_PM # to do
VIDEO_PM_OPT = None # to do
VIDEO_SC = '2024_video_SC.xml'
VIDEO_SC_DV = '2024_video_SC_opt.xml' # to do
VIDEO_SC_HDV = '2024_video_SC_opt.xml' # to do
VIDEO_SC_OPT = '2024_video_SC_opt.xml' # in progress

LOGGER = logging.getLogger(__name__)

def _configure_logging():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def dir_exists(dir):
    dir_path = Path(dir).resolve()
    if not dir_path.exists():
        exit(f'\nERROR - directory not found: {dir}\n')
    return dir_path

def parse_args():
    parser = argparse.ArgumentParser(description='Batch-check assets against MediaConch policies. '
                                     'Assets *must* be packaged with valid JSON metadata '
                                     'according to NYPL specifications',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-a',
                        dest='ami_directory',
                        help='Path to directory of AMI (dir of bags or single bag)',
                        required=True,
                        type=dir_exists)
    parser.add_argument('-p',
                        dest='policies_dir',
                        help='Path to directory of MediaConch policies',
                        required=True,
                        type=dir_exists)
    parser.add_argument('-v',
                        choices=[1, 2, 3, 4, 5],
                        default='2',
                        dest='verbosity',
                        help='Verbosity of results:'
                        "\n  -v1 = show expanded results only when outcome is 'error'"
                        "\n  -v2 = expand 'fail' or 'error' results (DEFAULT)"
                        "\n  -v3 = expand 'warn', 'fail' or 'error' results"
                        "\n  -v4 = expand 'info', 'warn', 'fail' or 'error' results"
                        "\n  -v5 = expand 'pass', 'info', 'warn', 'fail' or 'error'",
                        type=int)
    parser.add_argument('-g',
                        choices=['d', 'n', 'o', 'p'],
                        default='d',
                        dest='grouping',
                        help='Grouping of results:'
                        '\n  -gd = group by Description (source/role/policy) (DEFAULT)'
                        '\n  -gn = No grouping'
                        '\n  -go = group by Outcome'
                        '\n  -gp = group by Policy')
    parser.add_argument('-f',
                        choices=['s', 'x'],
                        default='x',
                        dest='formatter',
                        help='Formatting of results:'
                        "\n  -fs = Simple MediaConch text formatting"
                        '\n  -fx = Enhanced text formatting (DEFAULT)')
    parser.add_argument('--pcm', 
                        help='Use analog audio policy for F1 PCM (else digital policy)',
                        action='store_true')
    parser.add_argument('--flex', # rename?
                        help="Relax film policies' audio rules (else strict silent/sound)",
                        action='store_true')
    return parser.parse_args()

def get_asset_paths(dir_path):
    non_asset_exts = ('.cue', '.gz', '.jpeg', '.jpg', '.json', '.old', '.scc')
    return sorted([item for item in dir_path.rglob('*.*') 
                   if 'data' in item.parts 
                   and not (item.suffix.lower() in non_asset_exts
                            or item.name.startswith('.'))])

def bold(text):
    return f'\033[1m{text}\033[0m'

def get_json_values(asset_path):
    json_path = asset_path.with_suffix('.json')
    try:
        with open(json_path, 'r', encoding='utf-8-sig') as jfile:
            data = json.load(jfile)
            return (data['source']['object']['type'], 
                    data['source']['object']['format'], 
                    data['asset']['fileRole'])
    except FileNotFoundError:
        LOGGER.error(f'{bold("JSON not found")}: {asset_path}')
    except KeyError:
        LOGGER.error(f'{bold("JSON invalid")}: {asset_path}')

def assign_audio_policy(jformat, jtype, f1):
    if re.search('optical', jtype):
        policy = AUDIO_OPTICAL
    elif re.search('digital', jtype):
        if jformat in ('dat', 'adat'):
            policy = AUDIO_DIGITAL_DAT
        elif f1 == True and re.search('pcm|da-88', jformat):
            policy = AUDIO_ANALOG
        else:
            policy = AUDIO_DIGITAL
    else:
        if re.search('cylinder', jformat):
            policy = AUDIO_ANALOG_CYLINDER
        else:
            policy = AUDIO_ANALOG
    return policy

def assign_film_policy(jformat, jrole, flex):

    def sort_mp_film(silent_pol, compsound_pol, flex_pol):
        if flex == True:
            policy = flex_pol
        elif re.search('silent', jformat):
            policy = silent_pol
        else:
            policy = compsound_pol
        return policy

    if re.search('full-coat|track', jformat):
        policy = AUDIO_ANALOG
    elif jrole == 'sc':
        policy = sort_mp_film(FILM_SC_SLNT, FILM_SC_COMP, FILM_SC_FLEX)
    elif jrole == 'mz':
        policy = sort_mp_film(FILM_MZ_SLNT, FILM_MZ_COMP, FILM_MZ_FLEX)
    else:
        if not re.search('35', jformat):
            policy = sort_mp_film(FILM16_PM_SLNT, FILM16_PM_COMP, FILM16_PM_FLEX)
        else:
            policy = sort_mp_film(FILM35_PM_SLNT, FILM35_PM_COMP, FILM35_PM_FLEX)
    return policy

def assign_video_policy(jformat, jrole, jtype):  

    def sort_video(vid_sc_pol, vid_pm_pol):
        if jrole == 'sc': 
            policy = vid_sc_pol
        else: 
            policy = vid_pm_pol
        return policy

    if re.search('optical', jtype):
        policy = sort_video(VIDEO_SC_OPT, VIDEO_PM_OPT)
    elif re.search('hdv', jformat):
        policy = sort_video(VIDEO_SC_HDV, VIDEO_PM_HDV)
    elif re.search('dv', jformat):
        policy = sort_video(VIDEO_SC_DV, VIDEO_PM_DV)
    else:
        policy = sort_video(VIDEO_SC, VIDEO_PM)
    return policy

def assign_policy(jvals, f1, flex):
    jtype, jformat, jrole = [item.lower() for item in jvals]
    if re.search('audio', jtype):
        policy = assign_audio_policy(jformat, jtype, f1)
    elif re.search('film', jtype):
        policy = assign_film_policy(jformat, jrole, flex)
    elif re.search('video', jtype):
        policy = assign_video_policy(jformat, jrole, jtype)
    else:
        policy = None
    return policy

def build_command(asset_path, policy, p_dir, flag):
    return ['mediaconch', '-p', p_dir.joinpath(policy), asset_path, f'-f{flag}']

def run_command(command):
    seconds = 300
    try:
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=seconds, text=True)
        return process.stdout
    except subprocess.TimeoutExpired:
        return f'Command timed out after {seconds} seconds'
    
def describe_asset(jvals, policy):
    return (f'{" -- ". join(jvals)} (policy = {policy})')

def report_sorted(df_arg, grp, idx):
    df = df_arg.copy()
    if grp == 'description':
        df.description = [describe_asset(x, y) for x, y in zip(df.json_values, df.policy)]
    df = df.set_index(idx)
    grping = df.groupby(grp)
    for k, vals in grping.groups.items():
        print(f'\n{bold(k)}:')
        for result in vals:
            print(result)

def set_verbosity(v):
    skip = ['pass', 'info', 'warn', 'fail']
    n = 1
    while n < v:
        skip.pop()
        n += 1
    return skip

def get_line(elem, skip, indent):
    outcome = elem.attrib['outcome']
    if outcome in skip:
        return None
    else:
        name = elem.attrib['name']
        pt = f"[{elem.get('type')}] " if elem.get('type') else ""
        act = f" [actual = {elem.get('actual')}]" if elem.get('actual') else ""
        return f'{indent}{outcome}: {pt}{name}{act}'

def get_details(elem, skip, indent, lines):
    line = get_line(elem, skip, indent)
    if line:
        lines.append(line)
        indent += '  '
        for child in elem:
            get_details(child, skip, indent, lines)
    return '\n'.join(lines)

def format_xml_result(asset_path, output, verbosity):
    indent = '   --  '
    try:
        my_xml = ET.fromstring(output).find('.//{https://mediaarea.net/mediaconch}policy')
        outcome = my_xml.attrib['outcome']
        details = get_details(my_xml, verbosity, indent, [])
    except SyntaxError:
        outcome = 'ERROR'
        details = f'{indent}{output}'
    except (AttributeError, KeyError):
        outcome = 'ERROR'
        details = f"{indent}XML result parse issue: try rerunning {Path(__file__).name} with flag '-fs'"
    return f'{outcome}! {asset_path}\n{details}'.rstrip()

def format_simple_result(asset_path, output, skip):
    result = output.rstrip('\n')
    if re.search ('!', result):
        pattern = f"^({'!|'.join(skip)}!)"
        if re.search(pattern, result):
            result = result.split('\n')[0]
    else:
        result = f'ERROR! {asset_path}\n   --  {result}'
    return result

def set_grouping(g):
    d = {'d': 'description',
         'n': None, 
         'o': 'outcome',
         'p': 'policy'}
    return d.get(g)

def report_results(df, g):
    grp = set_grouping(g)
    if not grp:
        print()
        for result in df.result:
            print(result)
    else:
        report_sorted(df, grp, 'result')

def summarize(asset_count, inelig_count, elig_count, outcome_list):
    prob = asset_count - inelig_count - elig_count
    print(f'\n{asset_count} AMI assets found and sorted for MediaConch eligibility:'
          f'\n\t{elig_count} eligible'
          f'\n\t{inelig_count} ineligible')
    if prob != 0:
        print(f'\t{prob} problems encountered during sorting: see ERRORs logged above')
    ctr = Counter(outcome_list)
    p_ct, i_ct, w_ct, f_ct, e_ct = [ctr[x] for x in ('pass', 'info', 'warn', 'fail', 'ERROR')]
    print(f'\n{elig_count} MediaConch checks run for eligible assets:'
          f'\n\t{p_ct} pass'
          f'\n\t{i_ct} info'
          f'\n\t{w_ct} warn'
          f'\n\t{f_ct} fail')
    if e_ct != 0:
        print(f'\t{e_ct} problems encountered during checks: see ERRORs in results above')

def main():
    _configure_logging()
    args = parse_args()
    cols = ['asset_path', 'json_values', 'policy', 'description', 'command', 'output', 'result', 'outcome']
    df = pd.DataFrame(columns=cols)

    print('\nSearching for AMI assets...')
    df.asset_path = get_asset_paths(args.ami_directory)
    asset_count = len(df)

    if asset_count > 0:
        print('\nAnalyzing JSONs...')
        df.json_values = [get_json_values(x) for x in df.asset_path]
    df = df.dropna(subset=['json_values'])
    json_count = len(df)
    
    if json_count > 0:
        print('\nAssigning MediaConch policies for eligible assets...')
        df.policy = [assign_policy(x, args.pcm, args.flex) for x in df.json_values]
    df_inelig = df[df.policy.isnull()]
    inelig_count = len(df_inelig)
    if inelig_count > 0:
        print(f'INFO - {bold("ineligible assets will be skipped")} (no policy for the following type/format/role combos):')
        report_sorted(df_inelig, 'description', 'asset_path')
    df = df.dropna(subset=['policy'])
    elig_count = len(df)
    
    if elig_count > 0:
        df.command = [build_command(x.asset_path, x.policy, args.policies_dir, args.formatter) for x in df.itertuples()]
        print('\nRunning MediaConch commands in subprocess...')
        df.output = [run_command(x) for x in tqdm(df.command)]
        vb = set_verbosity(args.verbosity)
        if args.formatter == 'x':
            df.result = [format_xml_result(x.asset_path, x.output, vb) for x in df.itertuples()]
        else:
            df.result = [format_simple_result(x.asset_path, x.output, vb) for x in df.itertuples()]
        df.outcome = [x.split('!')[0] for x in df.result]
        print('Results:')
        report_results(df, args.grouping)

    print(f'\n\nSummary for {args.ami_directory}:')
    summarize(asset_count, inelig_count, elig_count, df.outcome.tolist())
    print()

if __name__ == '__main__':
    main()
