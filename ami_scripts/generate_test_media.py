#!/usr/bin/env python3
import argparse
import subprocess
import os

def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate test media files")
    parser.add_argument('-d', '--destination', type=str, help='Destination for the test media files', required=True)
    parser.add_argument('-r', '--region', type=str, help='Region for the video files (ntsc or pal)', default='ntsc', choices=['ntsc', 'pal'])
    return parser.parse_args()

def prepare_test_files(args):
    if args.region == 'ntsc':
        video_res = '720x486'
        frame_rate = '30000/1001'
        dv_pixel_format = 'yuv411p'
    else:
        video_res = '720x576'
        frame_rate = '25'
        dv_pixel_format = 'yuv420p'

    test_files = [
        {
            'name': 'v210_pcm_s24le_48KHz',
            'video_codec': 'v210',
            'audio_codec': 'pcm_s24le',
            'video_res': video_res,
            'frame_rate': frame_rate,
            'channels': 2,
            'ext': '.mov'
        },
        {
            'name': 'ffv1_10bit_pcm_s24le_48KHz',
            'video_codec': 'ffv1',
            'video_options': '-pix_fmt yuv420p10le',
            'audio_codec': 'pcm_s24le',
            'video_res': video_res,
            'frame_rate': frame_rate,
            'channels': 2,
            'ext': '.mkv'
        },
        {
            'name': 'dv_pcm_s16le_48KHz',
            'video_codec': 'dvvideo',
            'video_options': '-pix_fmt ' + dv_pixel_format,
            'audio_codec': 'pcm_s16le',
            'video_res': '720x480',
            'frame_rate': frame_rate,
            'channels': 2,
            'ext': '.dv'
        },
        {
            'name': 'pcm_s24le_96KHz',
            'audio_codec': 'pcm_s24le',
            'audio_rate': '96k',
            'channels': 2,
            'ext': '.wav'
        },
        {
            'name': 'flac_96KHz',
            'audio_codec': 'flac',
            'audio_rate': '96k',
            'channels': 2,
            'ext': '.flac'
        }
    ]
    return test_files

def generate_test_files(destination_dir, test_files):
    for test_file in test_files:
        if 'video_codec' in test_file:
            # Generate video+audio file
            command = [
                'ffmpeg',
                '-f', 'lavfi', '-i', 'mandelbrot',
                '-f', 'lavfi', '-i', 'sine=frequency=1000:sample_rate=48000',
                '-c:v', test_file['video_codec'],
                *test_file.get('video_options', '').split(),
                '-s', test_file['video_res'],
                '-r', test_file['frame_rate'],
                '-c:a', test_file['audio_codec'],
                '-ac', str(test_file['channels']),
                '-t', '10',
                os.path.join(destination_dir, f"{test_file['name']}{test_file['ext']}")
            ]
        else:
            # Generate audio file
            command = [
                'ffmpeg',
                '-f', 'lavfi', '-i', f"sine=frequency=1000:sample_rate={test_file['audio_rate']}:duration=10",
                '-c:a', test_file['audio_codec'],
                '-sample_fmt', 's32',
                '-ac', str(test_file['channels']),
                '-t', '10',
                os.path.join(destination_dir, f"{test_file['name']}{test_file['ext']}")
            ]
        subprocess.run(command, check=True)

def main():
    args = parse_arguments()
    destination_dir = os.path.join(args.destination, "test_media")
    os.makedirs(destination_dir, exist_ok=True)
    test_files = prepare_test_files(args)
    generate_test_files(destination_dir, test_files)

if __name__ == "__main__":
    main()
