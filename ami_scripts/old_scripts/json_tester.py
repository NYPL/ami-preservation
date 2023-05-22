#!/usr/bin/env python3

import argparse
import os
import subprocess
import json
import codecs

def get_args():
    parser = argparse.ArgumentParser(description='Run a series of tests on NYPL JSON packages')
    parser.add_argument('-s', '--source',
                        help = 'path to the source directory files', required=True)
    args = parser.parse_args()
    return args

def get_directory(args):
    try:
        test_directory = os.listdir(args.source)
    except OSError:
        exit("please retry with a valid directory of media/json")
    source_directory = args.source
    return source_directory

def get_file_list(source_directory):
    json_list = []
    json_no_ext_list = []
    file_no_ext_list = []
    file_list = []
    for root, dirs, files in os.walk(source_directory):
        for file in files:
            if file.endswith('.json'):
                item_path = os.path.join(root, file)
                json = os.path.basename(item_path)
                json_list.append(item_path)
                json_no_ext = os.path.splitext(json)[0]
                json_no_ext_list.append(json_no_ext)
            if file.endswith(('.wav', '.mkv', '.mov', '.mp4', '.flac')):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_list.append(item_path)
                file_no_ext = os.path.splitext(filename)[0]
                file_no_ext_list.append(file_no_ext)
    print()
    print("===================================")
    print()
    print("Testing JSON/Media Equivalency....")
    print()
    print("# of JSON Files: {}".format(len(json_list)))
    print("# of Media Files: {}".format(len(file_list)))
    if set(json_no_ext_list) == set(file_no_ext_list):
        print("You've got an equal # of JSON and Media Files, with matching names")
    else:
        print("You've got a prob Bob:")
    for item in json_no_ext_list:
        if item not in file_no_ext_list:
            print("You're missing a media file for: {}".format(item))
        else:
            continue
    for item in file_no_ext_list:
        if item not in json_no_ext_list:
            print("You're missing a JSON file for: {}".format(item))
        else:
            continue
    print()
    return json_list, json_no_ext_list, file_list, file_no_ext_list

def test_audio_derivatives(source_directory):
    em_list = []
    pm_list = []
    for root, dirs, files in os.walk(source_directory):
        for file in files:
            if file.endswith(('em.wav', 'em.flac')):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_no_ext = os.path.splitext(filename)[0]
                list_no_role = file_no_ext.split('_')[0:3]
                file_no_role = '_'.join(list_no_role)
                em_list.append(file_no_role)
            if file.endswith(('pm.wav', 'pm.flac')):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_no_ext = os.path.splitext(filename)[0]
                list_no_role = file_no_ext.split('_')[0:3]
                file_no_role = '_'.join(list_no_role)
                pm_list.append(file_no_role)
    if pm_list:
        print("===================================")
        print()
        print("Testing Audio PM/EM Equivalency....")
        print()
        print("# of PMs: {}".format(len(pm_list)))
        print("# of EMs: {}".format(len(em_list)))
        if set(em_list) == set(pm_list):
            print("You've got an equal # of PMs and EMs, with matching names")
        else:
            print("You've got an unequal # of PMs and EMs")
        for item in pm_list:
            if item not in em_list:
                print("You're missing an EM for: {}".format(item))
            else:
                continue
        for item in em_list:
            if item not in pm_list:
                print("You're missing an PM for: {}".format(item))
            else:
                continue
    return em_list, pm_list

def test_video_derivatives(source_directory):
    mkv_list = []
    sc_list = []
    for root, dirs, files in os.walk(source_directory):
        for file in files:
            if file.endswith('.mkv'):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_no_ext = os.path.splitext(filename)[0]
                list_no_role = file_no_ext.split('_')[0:3]
                file_no_role = '_'.join(list_no_role)
                mkv_list.append(file_no_role)
            if file.endswith('.mp4'):
                item_path = os.path.join(root, file)
                filename = os.path.basename(item_path)
                file_no_ext = os.path.splitext(filename)[0]
                list_no_role = file_no_ext.split('_')[0:3]
                file_no_role = '_'.join(list_no_role)
                sc_list.append(file_no_role)
    if mkv_list:
        print("===================================")
        print()
        print("Testing Video PM/SC Equivalency....")
        print()
        print("# of PMs: {}".format(len(mkv_list)))
        print("# of SCs: {}".format(len(sc_list)))
        if set(sc_list) == set(mkv_list):
            print("You've got an equal # of PMs and SCs, with matching names")
        else:
            print("You've got an unequal # of PMs and SCs")
        for item in mkv_list:
            if item not in sc_list:
                print("You're missing an SC for: {}".format(item))
            else:
                continue
        for item in sc_list:
            if item not in mkv_list:
                print("You're missing an MKV for: {}".format(item))
            else:
                continue
    return mkv_list, sc_list

def test_json_mediainfo(json_list, file_list):
    print("===================================")
    print()
    print("Testing for Correct MediaInfo in JSON....")
    print()
    fails = []
    mediainfo_list = zip(sorted(file_list), sorted(json_list))
    for j_tuple in mediainfo_list:
        filename = j_tuple[0]
        media_json = j_tuple[1]
        name = filename.split('/')[-1]
        technicalFilename = name.split('.')[0]
        format = subprocess.check_output(
            [
                'mediainfo', '--Language=raw',
                '--Full', "--Inform=General;%Format%",
                filename
            ]
            ).rstrip()
        format = format.decode('UTF-8')
        date_raw = subprocess.check_output(
            [
                'mediainfo', '--Language=raw',
                '--Full', "--Inform=General;%File_Modified_Date%",
                filename
            ]
            ).rstrip()
        date = str(date_raw).split(' ')[1]

        with open(media_json, "r") as jsonFile:
            data = json.load(jsonFile)
            json_format = data['technical']['fileFormat']
            if json_format == "BWF":
                json_format = "Wave"
            if technicalFilename == data['technical']['filename'] and format == json_format and date == data['technical']['dateCreated']:
                print("PASS: {}".format(name))
            else:
                print("FAIL: {}".format(name))
                fails.append(name)
    print("You have {} FAILS: ".format(len(fails)))
    for item in fails:
        print(item)

def main():
  arguments = get_args()
  source = get_directory(arguments)
  list_of_json, list_of_json_no_ext, list_of_files, list_of_files_no_ext = get_file_list(source)
  list_pm, list_em = test_audio_derivatives(source)
  list_mkv, list_sc = test_video_derivatives(source)
  files = test_json_mediainfo(list_of_json, list_of_files)

if __name__ == '__main__':
  main()
  exit(0)
