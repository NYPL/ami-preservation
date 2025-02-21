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
        dv_video_res = '720x480'
    else:
        video_res = '720x576'
        frame_rate = '25'
        dv_pixel_format = 'yuv420p'
        dv_video_res = '720x576'

    test_files = [
        {
            'name': 'v210_pcm_s24le_48kHz',
            'video_codec': 'v210',
            'audio_codec': 'pcm_s24le',
            'video_res': video_res,
            'frame_rate': frame_rate,
            'channels': 2,
            'ext': '.mov'
        },
        {
            'name': 'ffv1_10bit_pcm_s24le_48kHz_1stereo',
            'video_codec': 'ffv1',
            'video_options': '-pix_fmt yuv420p10le',
            'audio_codec': 'pcm_s24le',
            'video_res': video_res,
            'frame_rate': frame_rate,
            'channels': 2,
            'ext': '.mkv'
        },
        {
            'name': 'ffv1_10bit_pcm_s24le_48kHz_2stereo',
            'video_codec': 'ffv1',
            'video_options': '-pix_fmt yuv420p10le',
            'audio_codec': 'pcm_s24le',
            'video_res': video_res,
            'frame_rate': frame_rate,
            'channels': 2,
            'ext': '.mkv',
            'dual_audio': True,
            'audio_freq1': '1000',  # first audio stream frequency
            'audio_freq2': '500'    # second audio stream frequency
        },
        {
            'name': 'dv_pcm_s16le_48kHz',
            'video_codec': 'dvvideo',
            'video_options': '-pix_fmt ' + dv_pixel_format,
            'audio_codec': 'pcm_s16le',
            'video_res': dv_video_res,
            'frame_rate': frame_rate,
            'channels': 2,
            'ext': '.dv'
        },
        {
            'name': 'pcm_s24le_96kHz_stereo',
            'audio_codec': 'pcm_s24le',
            'audio_rate': '96k',
            'channels': 2,
            'ext': '.wav'
        },
        {
            'name': 'flac_s24le_96kHz_stereo',
            'audio_codec': 'flac',
            'audio_rate': '96k',
            'channels': 2,
            'ext': '.flac'
        },
        {
            'name': 'ffv1_rawcooked_2K_gbrp10le',
            'video_res': '2048x1556',
            'frame_rate': '24',
            'pix_fmt': 'gbrp10le',
            'frames': 10,
            'ext': '.dpx'
        },
        {
            'name': 'ffv1_rawcooked_4K_gbrp16le',
            'video_res': '4096x3112',
            'frame_rate': '24',
            'pix_fmt': 'gbrp16le',
            'frames': 10,
            'ext': '.dpx'
        },
        {
            'name': 'prores_hq__pcm_s24le_48kHz',
            'video_codec': 'prores_ks',
            'video_options': '-profile:v 3 -pix_fmt yuv422p10le',  # ProRes HQ in 4:2:2
            'audio_codec': 'pcm_s24le',
            'video_res': video_res,
            'frame_rate': frame_rate,
            'channels': 2,
            'ext': '.mov'
        },
        {
            'name': 'h264_aac_mp4_1stereo',
            'video_codec': 'libx264',
            'video_options': '-movflags faststart -pix_fmt yuv420p -crf 21',
            'audio_codec': 'aac',
            'audio_options': '-b:a 320000 -ar 48000',
            'video_res': video_res,
            'frame_rate': frame_rate,
            'channels': 2,
            'ext': '.mp4'
        },
        {
            'name': 'h264_aac_mp4_2stereo',
            'video_codec': 'libx264',
            'video_options': '-movflags faststart -pix_fmt yuv420p -crf 21',
            'audio_codec': 'aac',
            'audio_options': '-b:a 320000 -ar 48000',
            'video_res': video_res,
            'frame_rate': frame_rate,
            'channels': 2,
            'ext': '.mp4',
            'dual_audio': True,
            'audio_freq1': '1000',
            'audio_freq2': '500'
        }
    ]

    # Prepend "pal_" to the file name if region is pal.
    if args.region == 'pal':
        for file_def in test_files:
            file_def['name'] = "pal_" + file_def['name']

    return test_files

def generate_test_files(destination_dir, test_files):
    for test_file in test_files:
        # For non-DPX files, output is a single file; DPX cases use a directory.
        output_file = os.path.join(destination_dir, f"{test_file['name']}{test_file['ext']}")
        
        if 'video_codec' in test_file:
            if test_file.get('dual_audio'):
                # Dual audio: use filter_complex to convert each audio stream to s32.
                command = [
                    'ffmpeg',
                    '-f', 'lavfi', '-i', 'mandelbrot',
                    '-f', 'lavfi', '-i', f"sine=frequency={test_file.get('audio_freq1', '1000')}:sample_rate=48000",
                    '-f', 'lavfi', '-i', f"sine=frequency={test_file.get('audio_freq2', '500')}:sample_rate=48000",
                    '-filter_complex', "[1:a]aformat=sample_fmts=s32[a1];[2:a]aformat=sample_fmts=s32[a2]",
                    '-map', '0:v', '-map', '[a1]', '-map', '[a2]',
                    '-c:v', test_file['video_codec']
                ]
                command += test_file.get('video_options', '').split()
                command += [
                    '-s', test_file['video_res'],
                    '-r', test_file['frame_rate'],
                    '-c:a', test_file['audio_codec']
                ]
                if 'audio_options' in test_file:
                    command += test_file.get('audio_options', '').split()
                command += [
                    '-ac', str(test_file['channels']),
                    '-t', '10',
                    output_file
                ]
            else:
                # Single audio: use the -af filter to convert to s32.
                command = [
                    'ffmpeg',
                    '-f', 'lavfi', '-i', 'mandelbrot',
                    '-f', 'lavfi', '-i', 'sine=frequency=1000:sample_rate=48000',
                    '-af', 'aformat=sample_fmts=s32',
                    '-c:v', test_file['video_codec']
                ]
                command += test_file.get('video_options', '').split()
                command += [
                    '-s', test_file['video_res'],
                    '-r', test_file['frame_rate'],
                    '-c:a', test_file['audio_codec']
                ]
                if 'audio_options' in test_file:
                    command += test_file.get('audio_options', '').split()
                command += [
                    '-ac', str(test_file['channels']),
                    '-t', '10',
                    output_file
                ]
        elif 'pix_fmt' in test_file:
            # Handle DPX test file generation.
            dpx_dir = os.path.join(destination_dir, test_file['name'])
            os.makedirs(dpx_dir, exist_ok=True)
            command = [
                'ffmpeg',
                '-f', 'lavfi', '-i', f"mandelbrot=size={test_file['video_res']}:rate={test_file['frame_rate']}",
                '-vframes', str(test_file['frames']),
                '-pix_fmt', test_file['pix_fmt'],
                '-y', os.path.join(dpx_dir, f"{test_file['name']}_%06d{test_file['ext']}")
            ]
            subprocess.run(command, check=True)
            # Convert DPX frames with rawcooked.
            command = [
                'rawcooked',
                '--no-check-padding',
                dpx_dir
            ]
            subprocess.run(command)
            # Delete DPX frames.
            for dpx_file in os.listdir(dpx_dir):
                if dpx_file.endswith('.dpx'):
                    os.remove(os.path.join(dpx_dir, dpx_file))
            if not os.listdir(dpx_dir):
                os.rmdir(dpx_dir)
            continue
        else:
            # Audio-only file generation.
            command = [
                'ffmpeg',
                '-f', 'lavfi', '-i', f"sine=frequency=1000:sample_rate={test_file['audio_rate']}:duration=10",
                '-c:a', test_file['audio_codec'],
                '-sample_fmt', 's32',
                '-ac', str(test_file['channels']),
                '-t', '10',
                output_file
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
