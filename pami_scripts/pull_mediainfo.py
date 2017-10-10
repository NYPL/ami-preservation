#!/usr/bin/env python3

from pymediainfo import MediaInfo
import argparse
import os
import glob
import logging
import csv

LOGGER = logging.getLogger(__name__)

def _make_parser():
    parser = argparse.ArgumentParser(description="Pull MediaInfo attributes from a bunch of video or audio files")
    parser.add_argument("-d", "--directory",
                        help = "path to folder full of media files",
                        required = False)
    parser.add_argument("-f", "--file",
                        help = "path to folder full of media files",
                        required = False)
    parser.add_argument("-o", "--output",
                        help = "path to save csv",
                        required = True)


    return parser


def main():
    parser = _make_parser()
    args = parser.parse_args()

    files_to_examine = []

    #validate that dir exists and add all files to queue
    if args.directory:
        if os.path.isdir(args.directory):
            glob_abspath = os.path.abspath(os.path.join(args.directory, '*'))
            for filename in glob.iglob(glob_abspath, recursive = True):
                if filename.endswith('.mkv') or filename.endswith('.mov') or filename.endswith('.wav') or filename.endswith('.mp4'):
                    files_to_examine.append(filename)

    if args.file:
        if os.path.isfile(args.file):
            filename = args.file
            if filename.endswith('.mkv') or filename.endswith('.mov') or filename.endswith('.wav') or filename.endswith('.mp4'):
                files_to_examine.append(filename)

    all_file_data = []

    if not files_to_examine:
        print('Error: Please enter a directory or single file')
    else:
        print('examining: {}'.format(', '.join(files_to_examine)))

    for path in files_to_examine:
        media_info = MediaInfo.parse(path)
        for track in media_info.tracks:
            if track.track_type == "General":
                file_data = [
                    '.'.join([track.file_name, track.file_extension]),
                    track.file_name,
                    track.file_extension,
                    track.file_size,
                    track.file_last_modification_date.split()[1],
                    track.format,
                    track.audio_format_list.split()[0],
                    track.codecs_video,
                    track.duration
                ]
                hours = track.duration // 3600000
                minutes = (track.duration % 3600000) // 60000
                seconds = (track.duration % 60000) // 1000
                ms = track.duration % 1000
                human_duration = "{:0>2}:{:0>2}:{:0>2}.{:0>3}".format(hours, minutes, seconds, ms)
                file_data.append(human_duration)
                print(file_data)
                all_file_data.append(file_data)

    with open(args.output, 'w') as f:
        md_csv = csv.writer(f)
        md_csv.writerow([
            'asset.referenceFilename',
            'technical.filename',
            'technical.extension',
            'technical.fileSize.measure',
            'technical.dateCreated',
            'technical.fileFormat',
            'technical.audioCodec',
            'technical.videoCodec',
            'technical.durationMilli.measure',
            'technical.durationHuman'
        ])
        md_csv.writerows(all_file_data)



if __name__ == "__main__":
    main()
