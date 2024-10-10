#!/usr/bin/env python3

import subprocess
import json
import sys

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
    streams = json.loads(result.stdout)['streams']
    return len(streams)

def generate_mpv_command(file_path, audio_stream_count):
    base_cmd = [
        'mpv',
        '--autofit=75%',
        '--geometry=+0+0',
        file_path,
        '--lavfi-complex='
    ]
    
    if audio_stream_count == 1:
        # Single audio stream: Video + one vectorscope + showvolume overlay
        filter_complex = (
            '[aid1]asplit=3[ao][a1][a2];'
            '[a1]avectorscope=s=480x480,format=yuv420p[vec];'
            '[vec]drawbox=x=0:y=0:w=iw:h=ih:color=green:t=2[vec_b];'
            '[vec_b]drawtext=fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-tw)/2:y=10:text=\'CH 1 + 2\'[vec_t];'
            '[a2]aformat=channel_layouts=stereo,showvolume=f=0.5:b=4:w=180:h=40[vol];'  # Further scaled-down showvolume
            '[vec_t][vol]overlay=x=10:y=H-h-10[vec_ov];'  # Overlay showvolume on vectorscope, oriented left
            '[vid1]scale=-1:480[vid];'
            '[vid][vec_ov]hstack=inputs=2[vo]'
        )
    elif audio_stream_count >= 2:
        # Multiple audio streams: Video + vectorscope + showvolume for each stream
        filter_complex = '[vid1]scale=-1:480[vid];'
        
        colors = ['green', 'blue', 'red', 'magenta', 'cyan']  # Add more colors if needed
        
        for i in range(1, audio_stream_count + 1):
            color = colors[(i-1) % len(colors)]
            channel_text = f'CH {2*i-1} + {2*i}'
            
            filter_complex += f'[aid{i}]asplit=3[ao{i}][a{i}][av{i}];'
            filter_complex += f'[a{i}]avectorscope=s=480x480,format=yuv420p[vec{i}];'
            filter_complex += f'[vec{i}]drawbox=x=0:y=0:w=iw:h=ih:color={color}:t=2[vec{i}_b];'
            filter_complex += f'[vec{i}_b]drawtext=fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-tw)/2:y=10:text=\'{channel_text}\'[vec{i}_t];'
            filter_complex += f'[av{i}]aformat=channel_layouts=stereo,showvolume=f=0.5:b=4:w=180:h=40[vol{i}];'  # Further scaled-down showvolume
            filter_complex += f'[vec{i}_t][vol{i}]overlay=x=10:y=H-h-10[vec{i}_ov];'  # Overlay showvolume on vectorscope, oriented left
        
        # Combine all audio outputs
        filter_complex += f'{"".join([f"[ao{i}]" for i in range(1, audio_stream_count + 1)])}amix=inputs={audio_stream_count}[ao];'
        
        # Stack video and vectorscopes with showvolume overlays horizontally
        filter_complex += f'[vid]{" ".join([f"[vec{i}_ov]" for i in range(1, audio_stream_count + 1)])}hstack=inputs={audio_stream_count + 1}[vo]'
    
    base_cmd[-1] += filter_complex
    return base_cmd

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <path_to_video_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    audio_stream_count = get_audio_stream_count(file_path)
    mpv_command = generate_mpv_command(file_path, audio_stream_count)
    
    print("Executing command:")
    print(" ".join(mpv_command))
    subprocess.run(mpv_command)

if __name__ == "__main__":
    main()
