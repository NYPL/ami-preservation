#!/usr/bin/env python3

import subprocess
import json
import sys
import argparse

def get_audio_stream_count(file_path):
    ffprobe_cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-select_streams', 'a',
        file_path
    ]
    
    result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
    streams = json.loads(result.stdout).get('streams', [])
    return len(streams)

def get_video_stream_count(file_path):
    ffprobe_cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-select_streams', 'v',
        file_path
    ]
    
    result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
    streams = json.loads(result.stdout).get('streams', [])
    return len(streams)

def check_mpv_installed():
    try:
        subprocess.run(['mpv', '--version'], capture_output=True, check=True)
    except FileNotFoundError:
        print("Error: mpv is not installed. Try running 'brew install mpv'.")
        sys.exit(1)

def generate_mpv_command(file_path, audio_stream_count, is_audio_only, is_video_only, showspectrum_stop):
    # Set the autofit value based on whether it's audio-only or not
    if is_audio_only:
        autofit_value = '60%'  # Adjusted to accommodate additional visualization
    else:
        autofit_value = '75%'

    base_cmd = [
        'mpv',
        f'--autofit={autofit_value}',
        '--geometry=+0+0',
        file_path,
        '--lavfi-complex='
    ]

    if is_audio_only:
        if audio_stream_count > 1:
            # Merge all audio streams
            filter_complex = (
                f'{"".join([f"[aid{i}]" for i in range(1, audio_stream_count + 1)])}'
                f'amerge=inputs={audio_stream_count}[amerged];'
                '[amerged]asplit=5[a1][a2][a3][a4][ao];'
            )
        else:
            # Single audio stream
            filter_complex = '[aid1]asplit=5[a1][a2][a3][a4][ao];'

        # Process ebur128 to get video output and handle audio output
        filter_complex += (
            '[a2]ebur128=video=1:meter=18[ebur_raw][ebur_audio];'
            '[ebur_audio]anullsink;'
            '[ebur_raw]scale=320x240[ebur];'
        )

        # Visualizations
        filter_complex += (
            # Avectorscope
            '[a1]avectorscope=s=320x240:scale=sqrt:draw=dot:rc=40,format=yuv420p[vec];'
            # Showspectrum with customizable upper frequency limit
            f'[a3]showspectrum=s=640x240:slide=1:mode=combined:color=viridis:'
            f'scale=cbrt:fscale=lin:start=0:stop={showspectrum_stop}[spec];'
            # Showvolume
            '[a4]showvolume=w=640:h=50:f=0.5:dm=1[vol];'
            # Stack avectorscope and ebur128 side by side
            '[vec][ebur]hstack=inputs=2[top];'
            # Stack showspectrum and showvolume vertically
            '[spec][vol]vstack=inputs=2[bottom];'
            # Stack top and bottom vertically to get final output
            '[top][bottom]vstack=inputs=2[vo]'
        )
    elif is_video_only:
        # Handle video-only files with no audio streams
        filter_complex = (
            '[vid1]split=2[vid1a][vid1b];'
            '[vid1a]scale=480:324,setsar=1,signalstats=out=brng:c=0x40e0d0,format=yuv420p[vid_scaled];'
            '[vid1b]scale=480:162,waveform=filter=lowpass:scale=ire:graticule=green:intensity=0.2:flags=numbers+dots[wave];'
            '[vid_scaled][wave]vstack=inputs=2[vo]'
        )
    else:
        # Video file with audio
        if audio_stream_count == 1:
            filter_complex = (
                '[aid1]asplit=3[ao][a1][a2];'
                '[a1]avectorscope=s=324x324,format=yuv420p[vec];'
                '[vec]drawbox=x=0:y=0:w=iw:h=ih:color=green:t=2[vec_b];'
                '[vec_b]drawtext=fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-tw)/2:y=10:text=\'CH 1+2\'[vec_t];'
                '[a2]aformat=channel_layouts=stereo,showvolume=f=0.5:b=4:w=180:h=40:dm=3[vol];'
                '[vid1]format=yuv420p,split=2[vid][vid_wave];'
                '[vid]scale=480:324,setsar=1,signalstats=out=brng:c=0x40e0d0,format=yuv420p[vid_scaled];'
                '[vid_wave]scale=960:162,setsar=1,waveform=filter=lowpass:scale=ire:graticule=green:intensity=0.2:flags=numbers+dots[wave];'
                '[vec_t][vol]overlay=x=10:y=H-h-10[vec_ov];'
                '[vec_ov]scale=480:324[vec_scaled];'
                '[vid_scaled][vec_scaled]hstack=inputs=2[video_and_scope];'
                '[video_and_scope][wave]vstack=inputs=2[vo]'
            )
        elif audio_stream_count >= 2:
            # Handle multiple audio streams
            filter_complex = '[vid1]split=2[vid][vid_wave];'
            filter_complex += '[vid]scale=480:324,setsar=1,signalstats=out=brng:c=0x40e0d0,format=yuv420p[vid_scaled];'

            colors = ['green', 'blue', 'red', 'magenta', 'cyan']

            for i in range(1, audio_stream_count + 1):
                color = colors[(i-1) % len(colors)]
                channel_text = f'CH {2*i-1}+{2*i}'

                filter_complex += f'[aid{i}]asplit=3[ao{i}][a{i}][av{i}];'
                filter_complex += f'[a{i}]avectorscope=s=324x324,format=yuv420p[vec{i}];'
                filter_complex += f'[vec{i}]drawbox=x=0:y=0:w=iw:h=ih:color={color}:t=2[vec{i}_b];'
                filter_complex += f'[vec{i}_b]drawtext=fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-tw)/2:y=10:text=\'{channel_text}\'[vec{i}_t];'
                filter_complex += f'[av{i}]aformat=channel_layouts=stereo,showvolume=f=0.5:b=4:w=180:h=40:dm=3[vol{i}];'
                filter_complex += f'[vec{i}_t][vol{i}]overlay=x=10:y=H-h-10[vec{i}_ov];'

            total_width = 480 + audio_stream_count * 324  # Adjusted total width
            filter_complex += f'[vid_wave]format=yuv420p,scale={total_width}:162,setsar=1,waveform=filter=lowpass:scale=ire:graticule=green:intensity=0.2:flags=numbers+dots[wave];'
            filter_complex += f'{"".join([f"[ao{i}]" for i in range(1, audio_stream_count + 1)])}amix=inputs={audio_stream_count}[ao];'
            filter_complex += f'[vid_scaled]{" ".join([f"[vec{i}_ov]" for i in range(1, audio_stream_count + 1)])}hstack=inputs={audio_stream_count + 1}[video_and_scope];'
            filter_complex += f'[video_and_scope][wave]vstack=inputs=2[vo]'
    
    base_cmd[-1] += filter_complex
    return base_cmd


def main():
    # Setup argument parser
    parser = argparse.ArgumentParser(description="Process video or audio with MPV and FFmpeg filters.")
    parser.add_argument('-f', '--file', required=True, help="Path to the media file")
    parser.add_argument('--showspectrum-stop', type=int, default=20000,
                        help="Set the upper frequency limit for showspectrum. Default is 20000.")

    args = parser.parse_args()
    file_path = args.file
    showspectrum_stop = args.showspectrum_stop

    # Check if mpv is installed
    check_mpv_installed()

    # Get audio and video stream counts
    audio_stream_count = get_audio_stream_count(file_path)
    video_stream_count = get_video_stream_count(file_path)

    # Determine if the file is audio-only or video-only
    is_audio_only = (video_stream_count == 0 and audio_stream_count > 0)
    is_video_only = (audio_stream_count == 0 and video_stream_count > 0)

    if audio_stream_count == 0 and video_stream_count == 0:
        print("Error: No audio or video streams found in the provided file.")
        sys.exit(1)

    # Generate and run mpv command
    mpv_command = generate_mpv_command(file_path, audio_stream_count, is_audio_only, is_video_only, showspectrum_stop)

    print("Executing command:")
    print(" ".join(mpv_command))
    subprocess.run(mpv_command)

if __name__ == "__main__":
    main()
