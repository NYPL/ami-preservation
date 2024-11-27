#!/usr/bin/env python3 

import logging
import argparse
from pathlib import Path
import pandas as pd
import json
import re
import subprocess
from tqdm import tqdm
import time

# Old MediaConch policies:
OLD_AUDIO_ANALOG = 'MediaConch_NYPL-FLAC_Analog.xml'
OLD_AUDIO_DIGITAL = 'MediaConch_NYPL-FLAC_Digital.xml'
OLD_FILM16_PM = 'MediaConch_NYPL_8-16mmFilmPM.xml'
OLD_FILM35_PM = 'MediaConch_NYPL_35mFilmPM.xml'
OLD_FILM_MZ = 'MediaConch_NYPL_filmMZ.xml'
OLD_FILM_SC = 'MediaConch_NYPL_filmSC.xml'
OLD_VIDEO_PM = 'MediaConch_NYPL_FFV1MKV.xml'
OLD_VIDEO_SC = 'MediaConch_NYPL_video_SC.xml'
OLD_VIDEO_PM_OPT = None

# New MediaConch policies:
AUDIO_ANALOG = OLD_AUDIO_ANALOG # to do
AUDIO_DIGITAL = OLD_AUDIO_DIGITAL # to do
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
VIDEO_PM_DV = VIDEO_PM # to do
VIDEO_PM_HDV = VIDEO_PM # to do
VIDEO_PM_OPT = OLD_VIDEO_PM_OPT # to do
VIDEO_SC = '2024_video_SC.xml'
VIDEO_SC_DV = '2024_video_SC_optdv.xml' # to do (!)
VIDEO_SC_HDV = '2024_video_SC_optdv.xml' # to do (!)
VIDEO_SC_OPT = '2024_video_SC_optdv.xml' # in progress

# policy mapping: new to old
POL_MAP = {
    AUDIO_ANALOG: OLD_AUDIO_ANALOG,
    AUDIO_DIGITAL: OLD_AUDIO_DIGITAL,
    FILM16_PM_COMP: OLD_FILM16_PM,
    FILM16_PM_FLEX: OLD_FILM16_PM,
    FILM16_PM_SLNT: OLD_FILM16_PM,
    FILM35_PM_COMP: OLD_FILM35_PM,
    FILM35_PM_FLEX: OLD_FILM35_PM,
    FILM35_PM_SLNT: OLD_FILM35_PM,
    FILM_MZ_COMP: OLD_FILM_MZ,
    FILM_MZ_FLEX: OLD_FILM_MZ,
    FILM_MZ_SLNT: OLD_FILM_MZ,
    FILM_SC_COMP: OLD_FILM_SC,
    FILM_SC_FLEX: OLD_FILM_SC,
    FILM_SC_SLNT: OLD_FILM_SC,
    VIDEO_PM: OLD_VIDEO_PM,
    VIDEO_PM_DV: OLD_VIDEO_PM,
    VIDEO_PM_HDV: OLD_VIDEO_PM,
    VIDEO_PM_OPT: OLD_VIDEO_PM_OPT,
    VIDEO_SC: OLD_VIDEO_SC, 
    VIDEO_SC_DV: OLD_VIDEO_SC,
    VIDEO_SC_HDV: OLD_VIDEO_SC,
    VIDEO_SC_OPT: OLD_VIDEO_SC
}

LOGGER = logging.getLogger(__name__)

SLP = .025

def _configure_logging():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def parse_args():

    def dir_exists(dir):
        dir_path = Path(dir)
        if not dir_path.exists():
            exit(f'\nERROR - directory not found: {dir}\n')
        return dir_path
    
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
                        choices=[1, 2, 3],
                        default='2',
                        dest='verbosity',
                        help='Verbosity of results:'
                        '\n  -v1 = shorten all results to one line'
                        '\n  -v2 = shorten "pass!" results only (DEFAULT)'
                        '\n  -v3 = show full results for all outcomes',
                        type=int)
    parser.add_argument('-g',
                        choices=['n', 'o', 'p', 's'],
                        default='s',
                        dest='grouping',
                        help='Grouping of results:'
                        '\n  -gn = No grouping'
                        '\n  -go = group by Outcome'
                        '\n  -gp = group by Policy'
                        '\n  -gs = group by Source object + policy (DEFAULT)')
    parser.add_argument('--old',
                        help='Use old/original policies (instead of new/current)',
                        action='store_true')
    parser.add_argument('--f1',
                        help='Use analog audio policy for F1 PCM (instead of digital)',
                        action='store_true')
    parser.add_argument('--flex',
                        help='Use flexible film policies (instead of sep sound/silent)',
                        action='store_true')
    return parser.parse_args()

def get_asset_paths(dir_path):
    non_asset_exts = ('.cue', '.framemd5', '.jpeg', '.jpg', '.json', '.old', '.scc', '.txt')
    return sorted([item for item in dir_path.rglob('*') 
                   if (item.is_file() and 
                       not (item.name.startswith('.') or 
                            item.suffix.lower() in non_asset_exts))])

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
        time.sleep(SLP)
    except KeyError:
        LOGGER.error(f'{bold("JSON invalid")}: {asset_path}')
        time.sleep(SLP)

def assign_audio_policy(jtype):
    if re.search('digital|optical', jtype):
        policy = AUDIO_DIGITAL
    else:
        policy = AUDIO_ANALOG
    return policy

def assign_film_policy(jformat, jrole):

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

def assign_policy(jvals):
    jtype, jformat, jrole = [item.lower() for item in jvals]
    if re.search('audio', jtype):
        policy = assign_audio_policy(jtype)
    elif re.search('film', jtype):
        policy = assign_film_policy(jformat, jrole)
    elif re.search('video', jtype):
        policy = assign_video_policy(jformat, jrole, jtype)
    else:
        policy = None
    return policy

def except_f1(jvals, policy):
    if re.search('pcm', jvals[1].lower()):
        policy = AUDIO_ANALOG
    return policy

def get_old_policy(asset_path, policy):
    try:
        policy = POL_MAP[policy]
    except KeyError:
        LOGGER.warning(f'{bold("old policy not found")}, new policy will be used: {asset_path}')
        time.sleep(SLP)
    return policy

def flex_film(policy):
    if policy in (FILM_SC_COMP, FILM_SC_SLNT):
        policy = FILM_SC_FLEX
    if policy in (FILM_MZ_COMP, FILM_MZ_SLNT):
        policy = FILM_MZ_FLEX
    if policy in (FILM16_PM_COMP, FILM16_PM_SLNT):
        policy = FILM16_PM_FLEX
    if policy in (FILM35_PM_COMP, FILM35_PM_SLNT):
        policy = FILM35_PM_FLEX
    return policy

def build_command(asset_path, policy, p_dir):
    return ['mediaconch', '-p', p_dir.joinpath(policy), asset_path]

def run_command(command):
    seconds = 300
    try:
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=seconds, text=True)
        return process.stdout
    except subprocess.TimeoutExpired:
        return f'Command timed out after {seconds} seconds'

def shorten_result(result):
    return result.split('\n')[0]

def format_result(asset_path, output, verbosity):
    result = output.rstrip('\n')
    if 'pass!' in result:
        if verbosity < 3:
            result = shorten_result(result)
    elif 'fail!' in result:
        if verbosity < 2:
            result = shorten_result(result)
    else:
        result = f'ERROR! {asset_path}\n   --  {result}'
        if verbosity < 2:
            result = shorten_result(result)
    return result

def describe_asset(jvals, policy):
    return (f'{" -- ". join(jvals)} (policy = {policy})')

def bold(text):
    return f'\033[1m{text}\033[0m'

def report_sorted(df_arg, grp, idx):
    df = df_arg.copy()
    if grp == 'description':
        df.description = [describe_asset(x, y) for x, y in zip(df.json_values, df.policy)]
    df = df.set_index(idx)
    grping = df.groupby(grp)
    for k, vals in grping.groups.items():
        print(f'\n{bold(k)}:')
        for v in vals:
            print(v)
            time.sleep(SLP)

def report_results(df, g):
    if g == 'n':
        print()
        for r in df.result:
            print(r)
            time.sleep(SLP)
    else:
        d = {'o': 'outcome',
             'p': 'policy',
             's': 'description'}
        grp = d.get(g)
        report_sorted(df, grp, 'result')

def summarize(asset_count, inelig_count, elig_count, outcome_list):
    prob = asset_count - inelig_count - elig_count
    print(f'\n{asset_count} AMI assets found and sorted for MediaConch eligibility:'
          f'\n\t{elig_count} eligible'
          f'\n\t{inelig_count} ineligible')
    if prob != 0:
        print(f'\t{prob} problems encountered during sorting: see ERRORs logged above')
    p_count = outcome_list.count('pass')
    f_count = outcome_list.count('fail')
    e_count = elig_count - p_count - f_count
    print(f'\n{elig_count} MediaConch checks run for eligible assets:'
          f'\n\t{p_count} pass'
          f'\n\t{f_count} fail')
    if e_count != 0:
        print(f'\t{e_count} problems encountered during checks: see ERRORs in results above')

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
        df.policy = [assign_policy(x) for x in df.json_values]
        if args.flex == True:
            df.policy = [flex_film(x) for x in df.policy]
        if args.f1 == True:
            df.policy = [except_f1(x, y) for x, y in zip(df.json_values, df.policy)]
        if args.old == True:
            df.policy = [get_old_policy(x, y) for x, y in zip(df.asset_path, df.policy)]
    df_inelig = df[df.policy.isnull()]
    inelig_count = len(df_inelig)
    if inelig_count > 0:
        print(f'INFO - {bold("ineligible assets will be skipped")} (no policy for the following type/format/role combos):')
        time.sleep(2.5)
        report_sorted(df_inelig, 'description', 'asset_path')
    df = df.dropna(subset=['policy'])
    elig_count = len(df)
    
    if elig_count > 0:
        df.command = [build_command(x, y, args.policies_dir) for x, y in zip(df.asset_path, df.policy)]
        print('\nRunning MediaConch commands in subprocess...')
        df.output = [run_command(x) for x in tqdm(df.command)]
        df.result = [format_result(x, y, args.verbosity) for x, y in zip(df.asset_path, df.output)]
        df.outcome = [x.split('!')[0] for x in df.result]
        print('Results:')
        report_results(df, args.grouping)

    print(f'\n\nSummary for {args.ami_directory}:')
    summarize(asset_count, inelig_count, elig_count, df.outcome.tolist())
    print()

if __name__ == '__main__':
    main()